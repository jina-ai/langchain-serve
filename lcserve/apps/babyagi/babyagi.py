import asyncio
from collections import deque
from typing import Any, Dict, List, Literal, Optional, Union

from fastapi import WebSocket
from langchain import LLMChain, OpenAI, PromptTemplate, SerpAPIWrapper
from langchain.agents import AgentExecutor, Tool, ZeroShotAgent
from langchain.agents.load_tools import get_all_tool_names, load_tools
from langchain.chains.base import Chain
from langchain.docstore import InMemoryDocstore
from langchain.embeddings import OpenAIEmbeddings
from langchain.llms import BaseLLM
from langchain.vectorstores import FAISS
from langchain.vectorstores.base import VectorStore
from pydantic import BaseModel, Field


def get_vectorstore():
    import faiss

    # Define your embedding model
    embeddings_model = OpenAIEmbeddings()

    embedding_size = 1536
    index = faiss.IndexFlatL2(embedding_size)
    return FAISS(embeddings_model.embed_query, index, InMemoryDocstore({}), {})


class TaskCreationChain(LLMChain):
    """Chain to generates tasks."""

    @classmethod
    def from_llm(cls, llm: BaseLLM, verbose: bool = True) -> LLMChain:
        """Get the response parser."""
        task_creation_template = (
            "You are an task creation AI that uses the result of an execution agent"
            " to create new tasks with the following objective: {objective},"
            " The last completed task has the result: {result}."
            " This result was based on this task description: {task_description}."
            " These are incomplete tasks: {incomplete_tasks}."
            " Based on the result, create new tasks to be completed"
            " by the AI system that do not overlap with incomplete tasks."
            " Return the tasks as an array."
        )
        prompt = PromptTemplate(
            template=task_creation_template,
            input_variables=[
                "result",
                "task_description",
                "incomplete_tasks",
                "objective",
            ],
        )
        return cls(prompt=prompt, llm=llm, verbose=verbose)


class TaskPrioritizationChain(LLMChain):
    """Chain to prioritize tasks."""

    @classmethod
    def from_llm(cls, llm: BaseLLM, verbose: bool = True) -> LLMChain:
        """Get the response parser."""
        task_prioritization_template = (
            "You are an task prioritization AI tasked with cleaning the formatting of and reprioritizing"
            " the following tasks: {task_names}."
            " Consider the ultimate objective of your team: {objective}."
            " Do not remove any tasks. Return the result as a numbered list, like:"
            " #. First task"
            " #. Second task"
            " Start the task list with number {next_task_id}."
        )
        prompt = PromptTemplate(
            template=task_prioritization_template,
            input_variables=["task_names", "next_task_id", "objective"],
        )
        return cls(prompt=prompt, llm=llm, verbose=verbose)


def get_default_tools(llm: OpenAI) -> List[Tool]:
    """Get the default tools."""
    todo_prompt = PromptTemplate.from_template(
        "You are a planner who is an expert at coming up with a todo list for a given objective. Come up with a todo list for this objective: {objective}"
    )
    todo_chain = LLMChain(llm=llm, prompt=todo_prompt)
    search = SerpAPIWrapper()
    return [
        Tool(
            name="Search",
            func=search.run,
            description="useful for when you need to answer questions about current events",
        ),
        Tool(
            name="TODO",
            func=todo_chain.run,
            description="useful for when you need to come up with todo lists. Input: an objective to create a todo list for. Output: a todo list for that objective. Please be very clear what the objective is!",
        ),
    ]


def get_zero_shot_agent_prompt(tools: List[Tool]) -> PromptTemplate:
    """Get the prompt for the zero shot agent."""
    prefix = """You are an AI who performs one task based on the following objective: {objective}. Take into account these previously completed tasks: {context}."""
    suffix = """Question: {task}
    {agent_scratchpad}"""
    return ZeroShotAgent.create_prompt(
        tools,
        prefix=prefix,
        suffix=suffix,
        input_variables=["objective", "task", "context", "agent_scratchpad"],
    )


def get_next_task(
    task_creation_chain: LLMChain,
    result: Dict,
    task_description: str,
    task_list: List[str],
    objective: str,
) -> List[Dict]:
    """Get the next task."""
    incomplete_tasks = ", ".join(task_list)
    response = task_creation_chain.run(
        result=result,
        task_description=task_description,
        incomplete_tasks=incomplete_tasks,
        objective=objective,
    )
    new_tasks = response.split('\n')
    return [{"task_name": task_name} for task_name in new_tasks if task_name.strip()]


def prioritize_tasks(
    task_prioritization_chain: LLMChain,
    this_task_id: int,
    task_list: List[Dict],
    objective: str,
) -> List[Dict]:
    """Prioritize tasks."""
    task_names = [t["task_name"] for t in task_list]
    next_task_id = int(this_task_id) + 1
    response = task_prioritization_chain.run(
        task_names=task_names, next_task_id=next_task_id, objective=objective
    )
    new_tasks = response.split('\n')
    prioritized_task_list = []
    for task_string in new_tasks:
        if not task_string.strip():
            continue
        task_parts = task_string.strip().split(".", 1)
        if len(task_parts) == 2:
            task_id = task_parts[0].strip()
            task_name = task_parts[1].strip()
            prioritized_task_list.append({"task_id": task_id, "task_name": task_name})
    return prioritized_task_list


def _get_top_tasks(vectorstore, query: str, k: int) -> List[str]:
    """Get the top k tasks based on the query."""
    results = vectorstore.similarity_search_with_score(query, k=k)
    if not results:
        return []
    sorted_results, _ = zip(*sorted(results, key=lambda x: x[1], reverse=True))
    return [str(item.metadata['task']) for item in sorted_results]


def execute_task(
    vectorstore, execution_chain: LLMChain, objective: str, task: str, k: int = 5
) -> str:
    """Execute a task."""
    context = _get_top_tasks(vectorstore, query=objective, k=k)
    return execution_chain.run(objective=objective, context=context, task=task)


class TaskDetails(BaseModel):
    id: str = Field(..., alias="task_id")
    name: str = Field(..., alias="task_name")
    current: bool = False


class TaskResult(BaseModel):
    id: str
    name: str
    result: str


class BabyAGI(Chain, BaseModel):
    """Controller model for the BabyAGI agent."""

    websocket: Optional[WebSocket] = Field(None)
    task_list: deque = Field(default_factory=deque)
    task_creation_chain: TaskCreationChain = Field(...)
    task_prioritization_chain: TaskPrioritizationChain = Field(...)
    execution_chain: AgentExecutor = Field(...)
    task_id_counter: int = Field(1)
    vectorstore: VectorStore = Field(init=False)
    max_iterations: Optional[int] = None
    interactive: bool = False

    class Config:
        """Configuration for this pydantic object."""

        arbitrary_types_allowed = True

    def add_task(self, task: Dict):
        self.task_list.append(task)

    async def send_ws_message(self, message: Union[str, TaskDetails, TaskResult]):
        if self.websocket is not None:
            if isinstance(message, (TaskDetails, TaskResult)):
                await self.websocket.send_text(message.json())
            else:
                await self.websocket.send_json(
                    {'result': message, 'error': '', 'stdout': ''}
                )
        print(message)

    async def asend_task_list(self, task: Dict):
        await self.send_ws_message(TaskDetails(**task, current=True))
        for t in self.task_list:
            await self.send_ws_message(TaskDetails(**t))

    def send_task_list(self, task: Dict):
        asyncio.run(self.asend_task_list(task))

    async def asend_task_result(self, task: Dict, result: str):
        await self.send_ws_message(
            TaskResult(id=task["task_id"], name=task["task_name"], result=result)
        )

    def send_task_result(self, task: Dict, result: str):
        asyncio.run(self.asend_task_result(task, result))

    def print_task_ending(self):
        print("\n*****TASK ENDING*****\n")

    def should_continue(self) -> bool:
        ans = input("Do you want to continue? (y/n): ")
        if ans.lower() == "n":
            return False
        return True

    @property
    def input_keys(self) -> List[str]:
        return ["objective"]

    @property
    def output_keys(self) -> List[str]:
        return []

    def _call(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Run the agent."""
        objective = inputs['objective']
        first_task = inputs.get("first_task", "Make a todo list")
        self.add_task({"task_id": 1, "task_name": first_task})
        num_iters = 0
        while True:
            if self.task_list:
                # Step 1: Pull the first task
                task = self.task_list.popleft()
                self.send_task_list(task)

                # Step 2: Execute the task
                result = execute_task(
                    self.vectorstore, self.execution_chain, objective, task["task_name"]
                )
                this_task_id = int(task["task_id"])
                self.send_task_result(task, result)

                # Step 3: Store the result in Pinecone
                result_id = f"result_{task['task_id']}"
                self.vectorstore.add_texts(
                    texts=[result],
                    metadatas=[{"task": task["task_name"]}],
                    ids=[result_id],
                )

                # Step 4: Create new tasks and reprioritize task list
                new_tasks = get_next_task(
                    self.task_creation_chain,
                    result,
                    task["task_name"],
                    [t["task_name"] for t in self.task_list],
                    objective,
                )
                for new_task in new_tasks:
                    self.task_id_counter += 1
                    new_task.update({"task_id": self.task_id_counter})
                    self.add_task(new_task)

                self.task_list = deque(
                    prioritize_tasks(
                        self.task_prioritization_chain,
                        this_task_id,
                        list(self.task_list),
                        objective,
                    )
                )
            num_iters += 1

            if self.interactive:
                if not self.should_continue():
                    self.print_task_ending()
                    break
            else:
                if self.max_iterations is not None and num_iters == self.max_iterations:
                    self.print_task_ending()
                    break
        return {}

    @classmethod
    def from_llm(
        cls,
        llm: BaseLLM,
        vectorstore: VectorStore,
        tools: List[Tool],
        websocket: WebSocket = None,
        verbose: bool = False,
        **kwargs,
    ) -> "BabyAGI":
        """Initialize the BabyAGI Controller."""
        task_creation_chain = TaskCreationChain.from_llm(llm, verbose=verbose)
        task_prioritization_chain = TaskPrioritizationChain.from_llm(
            llm, verbose=verbose
        )
        llm_chain = LLMChain(llm=llm, prompt=get_zero_shot_agent_prompt(tools))
        tool_names = [tool.name for tool in tools]

        agent = ZeroShotAgent(llm_chain=llm_chain, allowed_tools=tool_names)
        agent_executor = AgentExecutor.from_agent_and_tools(
            agent=agent, tools=tools, verbose=True
        )
        return cls(
            websocket=websocket,
            task_creation_chain=task_creation_chain,
            task_prioritization_chain=task_prioritization_chain,
            execution_chain=agent_executor,
            vectorstore=vectorstore,
            **kwargs,
        )


class CustomTool(BaseModel):
    name: str
    prompt: str
    description: str

    def to_tool(self, llm: OpenAI) -> Tool:
        return Tool(
            name=self.name,
            func=LLMChain(
                llm=llm, prompt=PromptTemplate.from_template(self.prompt)
            ).run,
            description=self.description,
        )


class PredefinedTools(BaseModel):
    names: List[Literal[tuple(get_all_tool_names())]]
    params: Dict[str, str]


def get_tools(
    llm: OpenAI,
    predefined_tools: PredefinedTools,
    custom_tools: List[CustomTool],
) -> List[Tool]:
    if predefined_tools is None or getattr(predefined_tools, 'names') is None:
        lc_tools = get_default_tools(llm)
    else:
        lc_tools = load_tools(
            tool_names=predefined_tools.names, llm=llm, **predefined_tools.params
        )

    if custom_tools is not None:
        for tool in custom_tools:
            lc_tools.append(tool.to_tool(llm))

    return lc_tools
