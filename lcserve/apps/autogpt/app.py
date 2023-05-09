from typing import List

from autogpt import CustomTool, PredefinedTools, get_agent, get_tools
from langchain import OpenAI
from langchain.callbacks import CallbackManager

from lcserve import serving


@serving(websocket=True)
async def autogpt(
    name: str,
    role: str,
    goals: List[str],
    predefined_tools: PredefinedTools = None,
    custom_tools: List[CustomTool] = None,
    **kwargs,
) -> str:
    websocket = kwargs["websocket"]
    streaming_handler = kwargs['streaming_handler']

    llm = OpenAI(
        temperature=0,
        verbose=True,
        streaming=True,
        callback_manager=CallbackManager([streaming_handler]),
    )
    lc_tools = get_tools(llm, predefined_tools, custom_tools)
    agent = get_agent(
        name=name, role=role, websocket=websocket, tools=lc_tools, llm=llm
    )
    return await agent.arun(goals)
