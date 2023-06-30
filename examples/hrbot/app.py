import os
from typing import Callable, List

import langchain
from langchain import LLMChain
from langchain.agents import AgentExecutor, ConversationalAgent
from langchain.llms import OpenAI
from langchain.memory import ChatMessageHistory
from langchain.tools import Tool

from lcserve import SlackBot, get_memory, serving, slackbot

try:
    from gdrive import get_gdrive_service, list_files_in_gdrive
except ImportError:
    from .gdrive import get_gdrive_service, list_files_in_gdrive


try:
    from helper import index_pdfs_and_save, load_tools_from_disk
except ImportError:
    from .helper import index_pdfs_and_save, load_tools_from_disk


def update_cache(path):
    from langchain.cache import SQLiteCache

    langchain.llm_cache = SQLiteCache(database_path=os.path.join(path, "llm_cache.db"))


def get_hrbot_prefix() -> str:
    return """\
You are an HR bot on FutureSight AI's Slack workspace, and your role is to provide assistance to employees of FutureSight AI. \
Your task is to help employees with HR-related inquiries, such as questions about benefits, policies, and procedures. \
For any questions based on facts, you're allowed only to use the tools available to you. \
Feel free to use bullet points if you think it will help you answer the question. \
If you don't know the answer to a question, please ask the HR team.


TOOLS:
------

You have access to the following tools:"""


def refresh_gdrive_index(workspace: str, reply: Callable = None, **kwargs):
    llm = OpenAI(temperature=0, verbose=True)
    service = get_gdrive_service()
    pdf_files = list_files_in_gdrive(service, mime_types=['application/pdf'])

    index_pdfs_and_save(
        service=service,
        pdf_files=pdf_files,
        basedir=workspace,
        llm=llm,
    )
    if reply:
        reply("Refreshed, re-indexed and re-created tools for all PDFs in GDrive")


@serving
def refresh(**kwargs) -> str:
    workspace = kwargs['workspace']
    update_cache(workspace)
    refresh_gdrive_index(workspace=workspace)
    return "Refreshed, re-indexed and re-created tools for all PDFs in GDrive"


@slackbot(
    commands={
        '/refresh-gdrive-index': refresh_gdrive_index,
    }
)
def hrbot(
    message: str,
    history: ChatMessageHistory,
    tools: List[Tool],
    reply: Callable,
    workspace: str,
    **kwargs,
):
    llm = OpenAI(temperature=0, verbose=True)
    update_cache(workspace)
    tools.extend(load_tools_from_disk(llm=llm, path=workspace))
    prompt = ConversationalAgent.create_prompt(
        tools=tools,
        prefix=get_hrbot_prefix(),
        suffix=SlackBot.get_agent_prompt_suffix(),
    )

    memory = get_memory(history)
    agent = ConversationalAgent(
        llm_chain=LLMChain(llm=llm, prompt=prompt),
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
