import os
from typing import Callable, List

import langchain
from langchain.agents import AgentExecutor, ConversationalAgent
from langchain.callbacks.manager import CallbackManager
from langchain.memory import ChatMessageHistory
from langchain.prompts import PromptTemplate
from langchain.tools import Tool

from lcserve import get_memory, slackbot


def update_cache(path):
    from langchain.cache import SQLiteCache

    langchain.llm_cache = SQLiteCache(database_path=os.path.join(path, "llm_cache.db"))


@slackbot(openai_tracing=True)
def agent(
    message: str,
    prompt: PromptTemplate,
    history: ChatMessageHistory,
    tools: List[Tool],
    reply: Callable,
    tracing_handler,
    workspace: str,
    **kwargs,
):
    from langchain import LLMChain
    from langchain.chat_models import ChatOpenAI

    update_cache(workspace)
    memory = get_memory(history)
    agent = ConversationalAgent(
        llm_chain=LLMChain(
            llm=ChatOpenAI(temperature=0, verbose=True, callbacks=[tracing_handler]),
            prompt=prompt,
        ),
        allowed_tools=[tool.name for tool in tools],
    )
    agent_executor = AgentExecutor.from_agent_and_tools(
        agent=agent,
        tools=tools,
        memory=memory,
        verbose=True,
        max_iterations=4,
        handle_parsing_errors=True,
    )
    reply(agent_executor.run(message))
