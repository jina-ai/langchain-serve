from typing import Any, List

from babyagi import BabyAGI, CustomTool, PredefinedTools, get_tools, get_vectorstore
from langchain import OpenAI

# In order to be compatible with different langchain versions
try:
    from langchain.callbacks.manager import CallbackManager
except ImportError:
    from langchain.callbacks import CallbackManager

from lcserve import serving


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
        vectorstore=get_vectorstore(),
        tools=lc_tools,
        websocket=websocket,
        verbose=False,
        max_iterations=max_iterations,
        interactive=interactive,
    )

    agi({'objective': objective, 'first_task': first_task})
    return ''
