import os

from langchain.agents import initialize_agent, load_tools
from langchain.callbacks.base import CallbackManager
from langchain.chat_models import ChatOpenAI
from langchain.llms import OpenAI

from lcserve import serving


@serving(websocket=True)
def hitl(question: str, **kwargs) -> str:
    # Get the `streaming_handler` from `kwargs`. This is used to stream data to the client.
    streaming_handler = kwargs.get('streaming_handler')

    llm = ChatOpenAI(
        temperature=0.0,
        verbose=True,
        streaming=True,  # Pass `streaming=True` to make sure the client receives the data.
        callback_manager=CallbackManager(
            [streaming_handler]
        ),  # Pass the callback handler
    )
    math_llm = OpenAI(
        temperature=0.0,
        verbose=True,
        streaming=True,  # Pass `streaming=True` to make sure the client receives the data.
        callback_manager=CallbackManager(
            [streaming_handler]
        ),  # Pass the callback handler
    )
    tools = load_tools(
        ["human", "llm-math"],
        llm=math_llm,
    )

    agent_chain = initialize_agent(
        tools,
        llm,
        agent="zero-shot-react-description",
        verbose=True,
    )
    return agent_chain.run(question)
