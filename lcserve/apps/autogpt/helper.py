import asyncio
import json
from typing import Dict, List, Literal, Optional, TypeVar

from langchain.chains import llm


def _patch_colored_text(text: str, color: str) -> str:
    return text


llm.get_colored_text = _patch_colored_text


from fastapi import WebSocket
from langchain import LLMChain, OpenAI, PromptTemplate
from langchain.agents import Tool
from langchain.agents.load_tools import get_all_tool_names, load_tools
from langchain.chains.llm import LLMChain
from langchain.chat_models import ChatOpenAI
from langchain.chat_models.base import BaseChatModel
from langchain.experimental import AutoGPT
from langchain.experimental.autonomous_agents.autogpt.output_parser import (
    AutoGPTOutputParser,
    BaseAutoGPTOutputParser,
)
from langchain.experimental.autonomous_agents.autogpt.prompt import AutoGPTPrompt
from langchain.experimental.autonomous_agents.autogpt.prompt_generator import (
    FINISH_NAME,
)
from langchain.schema import AIMessage, Document, HumanMessage, SystemMessage
from langchain.tools.base import BaseTool
from langchain.vectorstores.base import VectorStoreRetriever
from pydantic import BaseModel, Field, ValidationError

T = TypeVar('T', bound='LCServeAutoGPT')


class LCServeHumanInputRun(BaseTool):
    """Tool that adds the capability to ask user for input."""

    websocket: WebSocket = Field(..., exclude=True)

    name = "Human"
    description = (
        "You can ask a human for guidance when you think you "
        "got stuck or you are not sure what to do next. "
        "The input should be a question for the human."
    )

    def _run(self, query: str) -> str:
        """Use the Human input tool."""
        asyncio.run(self._arun(query))

    async def _arun(self, query: str) -> str:
        """Use the Human tool asynchronously."""
        await self.websocket.send_json({'prompt': query})
        return await self.websocket.receive_text()


def get_default_tools():
    from langchain.agents import Tool
    from langchain.tools.file_management.read import ReadFileTool
    from langchain.tools.file_management.write import WriteFileTool
    from langchain.utilities import SerpAPIWrapper

    search = SerpAPIWrapper()
    tools = [
        Tool(
            name="search",
            func=search.run,
            description="useful for when you need to answer questions about current events. You should ask targeted questions",
        ),
        WriteFileTool(),
        ReadFileTool(),
    ]

    return tools


def get_vectorstore():
    from langchain.docstore import InMemoryDocstore
    from langchain.embeddings import OpenAIEmbeddings
    from langchain.vectorstores import FAISS

    # Define your embedding model
    embeddings_model = OpenAIEmbeddings()
    # Initialize the vectorstore as empty
    import faiss

    embedding_size = 1536
    index = faiss.IndexFlatL2(embedding_size)
    return FAISS(embeddings_model.embed_query, index, InMemoryDocstore({}), {})


class LCServeAutoGPT(AutoGPT):
    def __init__(self, websocket: WebSocket, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.websocket = websocket

    @classmethod
    def from_llm_and_tools(
        cls,
        websocket: WebSocket,
        ai_name: str,
        ai_role: str,
        memory: VectorStoreRetriever,
        tools: List[BaseTool],
        llm: BaseChatModel,
        human_in_the_loop: bool = False,
        output_parser: Optional[BaseAutoGPTOutputParser] = None,
    ) -> T:
        prompt = AutoGPTPrompt(
            ai_name=ai_name,
            ai_role=ai_role,
            tools=tools,
            input_variables=["memory", "messages", "goals", "user_input"],
            token_counter=llm.get_num_tokens,
        )
        chain = LLMChain(
            llm=llm,
            prompt=prompt,
            verbose=True,
            callback_manager=llm.callback_manager,
        )
        return cls(
            websocket,
            ai_name,
            memory,
            chain,
            output_parser or AutoGPTOutputParser(),
            tools,
            feedback_tool=LCServeHumanInputRun(websocket=websocket)
            if human_in_the_loop
            else None,
        )

    async def arun(self, goals: List[str]) -> str:
        user_input = (
            "Determine which next command to use, "
            "and respond using the format specified above:"
        )
        # Interaction Loop
        loop_count = 0
        while True:
            # Discontinue if continuous limit is reached
            loop_count += 1

            # Send message to AI, get response
            assistant_reply = await self.chain.arun(
                goals=goals,
                messages=self.full_message_history,
                memory=self.memory,
                user_input=user_input,
            )

            try:
                _assistant_reply = json.loads(assistant_reply)
            except json.decoder.JSONDecodeError:
                _assistant_reply = assistant_reply

            await self.websocket.send_json(_assistant_reply)
            self.full_message_history.append(HumanMessage(content=user_input))
            self.full_message_history.append(AIMessage(content=assistant_reply))

            # Get command name and arguments
            action = self.output_parser.parse(assistant_reply)
            tools = {t.name: t for t in self.tools}
            if action.name == FINISH_NAME:
                return action.args["response"]
            if action.name in tools:
                tool = tools[action.name]
                try:
                    observation = await tool.arun(action.args)
                except NotImplementedError:
                    observation = tool.run(action.args)
                except ValidationError as e:
                    observation = (
                        f"Validation Error in args: {str(e)}, args: {action.args}"
                    )
                except Exception as e:
                    observation = (
                        f"Error: {str(e)}, {type(e).__name__}, args: {action.args}"
                    )
                result = f"Command {tool.name} returned: {observation}"
            elif action.name == "ERROR":
                result = f"Error: {action.args}. "
            else:
                result = (
                    f"Unknown command '{action.name}'. "
                    f"Please refer to the 'COMMANDS' list for available "
                    f"commands and only respond in the specified JSON format."
                )

            memory_to_add = (
                f"Assistant Reply: {assistant_reply} " f"\nResult: {result} "
            )
            if self.feedback_tool is not None:
                feedback = await self.feedback_tool.arun(
                    'Waiting for feedback, OR pass "exit" to exit.'
                )
                if feedback in {"q", "stop", "exit"}:
                    print("EXITING")
                    return "EXITING"
                memory_to_add += feedback

            self.memory.add_documents([Document(page_content=memory_to_add)])
            self.full_message_history.append(SystemMessage(content=result))


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
        lc_tools = get_default_tools()
    else:
        lc_tools = load_tools(
            tool_names=predefined_tools.names, llm=llm, **predefined_tools.params
        )

    if custom_tools is not None:
        for tool in custom_tools:
            lc_tools.append(tool.to_tool(llm))

    return lc_tools


def get_agent(
    name: str,
    role: str,
    websocket: WebSocket,
    tools: List[Tool],
    llm: ChatOpenAI,
    human_in_the_loop: bool = False,
) -> LCServeAutoGPT:
    vectorstore = get_vectorstore()
    return LCServeAutoGPT.from_llm_and_tools(
        websocket=websocket,
        ai_name=name,
        ai_role=role,
        tools=tools,
        llm=llm,
        memory=vectorstore.as_retriever(),
        human_in_the_loop=human_in_the_loop,
    )
