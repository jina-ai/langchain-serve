import asyncio
from typing import Any

from fastapi import WebSocket
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from pydantic import BaseModel, ValidationError


class AsyncStreamingWebsocketCallbackHandler(StreamingStdOutCallbackHandler):
    def __init__(self, websocket: 'WebSocket', output_model: 'BaseModel'):
        super().__init__()
        self.websocket = websocket
        self.output_model = output_model

    @property
    def always_verbose(self) -> bool:
        return True

    @property
    def is_async(self) -> bool:
        return True

    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        try:
            data = self.output_model(result=token, error='').dict()
        except ValidationError:
            data = {'result': token, 'error': ''}
        await self.websocket.send_json(data)

    async def on_text(self, text: str, **kwargs: Any) -> None:
        try:
            data = self.output_model(result=text, error='').dict()
        except ValidationError:
            data = {'result': text, 'error': ''}
        await self.websocket.send_json(data)


class StreamingWebsocketCallbackHandler(AsyncStreamingWebsocketCallbackHandler):
    @property
    def is_async(self) -> bool:
        return False

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        asyncio.run(super().on_llm_new_token(token, **kwargs))

    def on_text(self, text: str, **kwargs: Any) -> None:
        asyncio.run(super().on_text(text, **kwargs))


class _HumanInput(BaseModel):
    prompt: str


class InputWrapper:
    """Wrapper for human input."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        websocket: 'WebSocket',
        recv_lock: asyncio.Lock,
    ):
        self.loop = loop
        self.websocket = websocket
        self.recv_lock = recv_lock

    async def __acall__(self, __prompt: str = ''):
        _human_input = _HumanInput(prompt=__prompt)
        async with self.recv_lock:
            await self.websocket.send_json(_human_input.dict())
        return await self.websocket.receive_text()

    def __call__(self, __prompt: str = ''):
        return asyncio.run_coroutine_threadsafe(
            self.__acall__(__prompt), self.loop
        ).result()


class PrintWrapper:
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        websocket: 'WebSocket',
        output_model: 'BaseModel',
    ):
        self.loop = loop
        self.websocket = websocket
        self.output_model = output_model

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        asyncio.run_coroutine_threadsafe(self.__acall__(*args, **kwds), self.loop)

    async def __acall__(self, *args: Any, **kwds: Any) -> Any:
        await self.websocket.send_json(
            self.output_model(result='', error='', stdout=' '.join(args)).dict()
        )


class BuiltinsWrapper:
    """Context manager to wrap builtins with websocket."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        websocket: 'WebSocket',
        output_model: 'BaseModel',
        wrap_print: bool = True,
        wrap_input: bool = True,
    ):
        self.loop = loop
        self.websocket = websocket
        self.output_model = output_model
        self._wrap_print = wrap_print
        self._wrap_input = wrap_input

    def __enter__(self):
        import builtins

        if self._wrap_print:
            self._print = builtins.print
            builtins.print = PrintWrapper(self.loop, self.websocket, self.output_model)

        if self._wrap_input:
            self._input = builtins.input
            builtins.input = InputWrapper(self.loop, self.websocket, asyncio.Lock())

    def __exit__(self, exc_type, exc_val, exc_tb):
        import builtins

        if self._wrap_print:
            builtins.print = self._print

        if self._wrap_input:
            builtins.input = self._input
