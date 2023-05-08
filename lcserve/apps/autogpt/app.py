import json
import asyncio
from typing import List, Optional, TypeVar

from langchain.experimental import AutoGPT
from langchain.chains.llm import LLMChain
from langchain.chat_models.base import BaseChatModel
from langchain.tools.base import BaseTool
from langchain.vectorstores.base import VectorStoreRetriever
from langchain.experimental.autonomous_agents.autogpt.output_parser import (
    AutoGPTOutputParser,
    BaseAutoGPTOutputParser,
)
from langchain.experimental.autonomous_agents.autogpt.prompt import AutoGPTPrompt
from langchain.experimental.autonomous_agents.autogpt.prompt_generator import (
    FINISH_NAME,
)
from langchain.schema import (
    AIMessage,
    Document,
    HumanMessage,
    SystemMessage,
)
from pydantic import ValidationError, Field
from fastapi import WebSocket

from lcserve import serving


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


def get_tools():
    from langchain.utilities import SerpAPIWrapper
    from langchain.agents import Tool
    from langchain.tools.file_management.write import WriteFileTool
    from langchain.tools.file_management.read import ReadFileTool

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
    from langchain.vectorstores import FAISS
    from langchain.docstore import InMemoryDocstore
    from langchain.embeddings import OpenAIEmbeddings

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
        output_parser: Optional[BaseAutoGPTOutputParser] = None,
    ) -> T:
        prompt = AutoGPTPrompt(
            ai_name=ai_name,
            ai_role=ai_role,
            tools=tools,
            input_variables=["memory", "messages", "goals", "user_input"],
            token_counter=llm.get_num_tokens,
        )
        chain = LLMChain(llm=llm, prompt=prompt, verbose=True)
        return cls(
            websocket,
            ai_name,
            memory,
            chain,
            output_parser or AutoGPTOutputParser(),
            tools,
            feedback_tool=LCServeHumanInputRun(websocket=websocket),
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
                feedback = await self.feedback_tool.arun('Input: ')
                if feedback in {"q", "stop", "exit"}:
                    print("EXITING")
                    return "EXITING"
                memory_to_add += feedback

            self.memory.add_documents([Document(page_content=memory_to_add)])
            self.full_message_history.append(SystemMessage(content=result))


def get_agent(websocket: WebSocket, streaming_handler) -> LCServeAutoGPT:
    from langchain.chat_models import ChatOpenAI
    from langchain.callbacks import CallbackManager

    tools = get_tools()
    vectorstore = get_vectorstore()
    return LCServeAutoGPT.from_llm_and_tools(
        websocket=websocket,
        ai_name="Tom",  # TODO: make this configurable
        ai_role="Assistant",  # TODO: make this configurable
        tools=tools,  # TODO: make this configurable
        llm=ChatOpenAI(
            temperature=0,
            verbose=True,
            streaming=True,
            callback_manager=CallbackManager([streaming_handler]),
        ),
        memory=vectorstore.as_retriever(),
    )


@serving(websocket=True)
async def autogpt(goals: List[str], **kwargs) -> str:
    websocket = kwargs["websocket"]
    streaming_handler = kwargs['streaming_handler']
    agent = get_agent(websocket, streaming_handler)
    return await agent.arun(goals)
