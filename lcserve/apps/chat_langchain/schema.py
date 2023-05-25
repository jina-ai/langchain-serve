from pydantic import BaseModel, validator

class ChatResponse(BaseModel):
    sender: str
    message: str
    type: str

    @validator('sender')
    def validate_sender(cls, v):
        if v not in ['bot', 'you']:
            raise ValueError('`sender` must be `bot` or `you`')
        return v

    @validator('type')
    def validate_type(cls, v):
        if v not in ['start', 'stream', 'end', 'error', 'info']:
            raise ValueError('`type` must be one of [`start`, `stream`, `end`, `error`, `info`]')