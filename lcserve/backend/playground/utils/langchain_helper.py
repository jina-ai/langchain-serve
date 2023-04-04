import asyncio

from fastapi import WebSocket
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.tools.human.tool import HumanInputRun
from pydantic import BaseModel, Extra


class AsyncStreamingWebsocketCallbackHandler(StreamingStdOutCallbackHandler):
    def __init__(self, websocket: 'WebSocket', output_model: 'BaseModel'):
        super().__init__()
        self.websocket = websocket
        self.output_model = output_model

    def is_async(self) -> bool:
        return True

    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        await self.websocket.send_json(self.output_model(result=token, error='').dict())


class StreamingWebsocketCallbackHandler(AsyncStreamingWebsocketCallbackHandler):
    def is_async(self) -> bool:
        return False

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        asyncio.run(super().on_llm_new_token(token, **kwargs))


class _HumanInput(BaseModel):
    prompt: str


class InputWrapper:
    """Wrapper for human input."""

    def __init__(self, websocket: 'WebSocket', recv_lock: asyncio.Lock):
        self.websocket = websocket
        self.recv_lock = recv_lock

    async def __acall__(self, __prompt: str = ''):
        _human_input = _HumanInput(prompt=__prompt)
        async with self.recv_lock:
            await self.websocket.send_json(_human_input.dict())
        return await self.websocket.receive_text()

    def __call__(self, __prompt: str = ''):
        from .helper import get_or_create_eventloop

        return get_or_create_eventloop().run_until_complete(self.__acall__(__prompt))
