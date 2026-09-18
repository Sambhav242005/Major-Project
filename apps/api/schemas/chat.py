from datetime import datetime

from pydantic import BaseModel


class ChatSessionCreate(BaseModel):
    title: str | None = None


class ChatSessionOut(BaseModel):
    id: str
    title: str | None
    created_at: datetime


class CitationOut(BaseModel):
    chunk_id: str
    document_id: str
    page_number: int | None
    filename: str | None


class ChatMessageOut(BaseModel):
    id: str
    role: str
    content: str
    citations: list[CitationOut] | None
    created_at: datetime


class ChatSessionResponse(BaseModel):
    session: ChatSessionOut
    messages: list[ChatMessageOut]


class ChatMessageCreate(BaseModel):
    message: str
