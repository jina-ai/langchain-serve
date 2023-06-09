import asyncio
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import WebSocket
from langchain.callbacks.base import BaseCallbackHandler
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.schema import LLMResult
from opentelemetry.trace import Span, Tracer, set_span_in_context
from pydantic import BaseModel, ValidationError


class TracingCallbackHandler(BaseCallbackHandler):
    def __init__(self, tracer: Tracer, parent_span: Span):
        super().__init__()
        self.tracer = tracer
        self.parent_span = parent_span

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any
    ) -> None:
        if not self.tracer:
            return

        prompts_len = 0
        operation = "langchain.on_llm_start"

        context = set_span_in_context(self.parent_span)
        with self.tracer.start_as_current_span("llm start", context=context) as span:
            span.set_attribute("otel.operation.name", operation)
            prompts_len += sum([len(prompt) for prompt in prompts])
            span.set_attribute("num_processed_prompts", len(prompts))
            span.set_attribute("prompts_len", prompts_len)

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        if not self.tracer:
            return

        operation = "langchain.on_llm_end"
        token_usage = response.llm_output["token_usage"]

        context = set_span_in_context(self.parent_span)
        with self.tracer.start_as_current_span("llm end", context=context) as span:
            span.set_attribute("otel.operation.name", operation)
            for k, v in token_usage.items():
                span.set_attribute(k, v)


class AsyncStreamingWebsocketCallbackHandler(StreamingStdOutCallbackHandler):
    def __init__(self, websocket: "WebSocket", output_model: "BaseModel"):
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
            data = self.output_model(result=token, error="").dict()
        except ValidationError:
            data = {"result": token, "error": ""}
        await self.websocket.send_json(data)

    async def on_text(self, text: str, **kwargs: Any) -> None:
        try:
            data = self.output_model(result=text, error="").dict()
        except ValidationError:
            data = {"result": text, "error": ""}
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
        websocket: "WebSocket",
        recv_lock: asyncio.Lock,
    ):
        self.loop = loop
        self.websocket = websocket
        self.recv_lock = recv_lock

    async def __acall__(self, __prompt: str = ""):
        _human_input = _HumanInput(prompt=__prompt)
        async with self.recv_lock:
            await self.websocket.send_json(_human_input.dict())
        return await self.websocket.receive_text()

    def __call__(self, __prompt: str = ""):
        return asyncio.run_coroutine_threadsafe(
            self.__acall__(__prompt), self.loop
        ).result()


class PrintWrapper:
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        websocket: "WebSocket",
        output_model: "BaseModel",
    ):
        self.loop = loop
        self.websocket = websocket
        self.output_model = output_model

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        asyncio.run_coroutine_threadsafe(self.__acall__(*args, **kwds), self.loop)

    async def __acall__(self, *args: Any, **kwds: Any) -> Any:
        await self.websocket.send_json(
            self.output_model(result="", error="", stdout=" ".join(args)).dict()
        )


class BuiltinsWrapper:
    """Context manager to wrap builtins with websocket."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        websocket: "WebSocket",
        output_model: "BaseModel",
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
