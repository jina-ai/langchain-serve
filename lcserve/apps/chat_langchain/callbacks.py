from langchain.callbacks.base import AsyncCallbackHandler
from schema import ChatResponse
from typing import Dict, Any, List


class QuestionGenCallbackHandler(AsyncCallbackHandler):
    def __int__(self, websocket):
        self.websocket = websocket

    async def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        resp = ChatResponse(sender='bot', message='Synthesizing question ...', type='info')
        await self.websocket.send_json(resp.dict())


class StreamingLLMCallbackHandler(AsyncCallbackHandler):
    def __int__(self, websocket):
        self.websocket = websocket

    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        resp = ChatResponse(sender='bot', message=token, type='stream')
        await self.websocket.send_json(resp.dict())


