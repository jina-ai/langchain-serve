from typing import Any, List

from langchain import OpenAI
from langchain.agents import Tool
from langchain.agents.load_tools import load_tools
from langchain.callbacks.base import CallbackManager
from lcserve import serving

from babyagi import BabyAGI, CustomTool, PredefinedTools, get_default_tools, vectorstore


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


@serving(websocket=True)
def baby_agi(
    objective: str,
    first_task: str = 'Make a todo list.',
    predefined_tools: PredefinedTools = None,
    custom_tools: List[CustomTool] = None,
    max_iterations: int = 1,
    interactive: bool = False,
    **kwargs: Any,
) -> str:
    websocket = kwargs.get('websocket')
    streaming_handler = kwargs.get('streaming_handler')

    llm = OpenAI(
        temperature=0,
        verbose=True,
        streaming=True,
        callback_manager=CallbackManager([streaming_handler]),
    )

    lc_tools = get_tools(llm, predefined_tools, custom_tools)
    agi = BabyAGI.from_llm(
        llm=llm,
        vectorstore=vectorstore,
        tools=lc_tools,
        websocket=websocket,
        verbose=False,
        max_iterations=max_iterations,
        interactive=interactive,
    )

    agi({'objective': objective, 'first_task': first_task})
    return ''
