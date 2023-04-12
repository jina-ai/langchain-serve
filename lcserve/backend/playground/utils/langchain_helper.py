import asyncio
from typing import Any

from fastapi import WebSocket
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from pydantic import BaseModel


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
        return asyncio.run(self.__acall__(__prompt))


class PrintWrapper:
    def __init__(self, websocket: 'WebSocket', output_model: 'BaseModel'):
        self.websocket = websocket
        self.output_model = output_model

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        asyncio.run(self.__acall__(*args, **kwds))

    async def __acall__(self, *args: Any, **kwds: Any) -> Any:
        await self.websocket.send_json(
            self.output_model(result='', error='', stdout=' '.join(args)).dict()
        )


class BuiltinsWrapper:
    """Context manager to wrap builtins with websocket."""

    def __init__(self, websocket: 'WebSocket', output_model: 'BaseModel'):
        self.websocket = websocket
        self.output_model = output_model

    def __enter__(self):
        import builtins

        self._print = builtins.print
        self._input = builtins.input
        builtins.print = PrintWrapper(self.websocket, self.output_model)
        builtins.input = InputWrapper(self.websocket, asyncio.Lock())

    def __exit__(self, exc_type, exc_val, exc_tb):
        import builtins

        builtins.print = self._print
        builtins.input = self._input
