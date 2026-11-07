import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: uuid.UUID | None = None
    message: str = Field(min_length=1, max_length=1000)


class ChatResponse(BaseModel):
    session_id: uuid.UUID
    reply: str
    cards: list[dict] = []
    appointments_changed: bool = False


class HistoryMessage(BaseModel):
    role: str
    content: str
    created_at: datetime
