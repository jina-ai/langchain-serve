"""Schemas for the chat app."""
from pydantic import BaseModel, validator

from docarray import BaseDoc
from docarray.typing import NdArray
from typing import Optional

class ChatResponse(BaseModel):
    """Chat response schema."""

    sender: str
    message: str
    type: str

    @validator("sender")
    def sender_must_be_bot_or_you(cls, v):
        if v not in ["bot", "you"]:
            raise ValueError("sender must be bot or you")
        return v

    @validator("type")
    def validate_message_type(cls, v):
        if v not in ["start", "stream", "end", "error", "info"]:
            raise ValueError("type must be start, stream or end")
        return v


class Document(BaseDoc):
    page_content: str
    metadata: dict
    embedding: Optional[NdArray[1536]]