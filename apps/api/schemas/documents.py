from datetime import datetime

from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    id: str
    filename: str
    status: str
    message: str


class DocumentChunkOut(BaseModel):
    id: str
    chunk_index: int
    page_number: int | None
    text: str
    token_count: int | None


class DocumentOut(BaseModel):
    id: str
    filename: str
    file_type: str
    status: str
    page_count: int | None
    error_message: str | None
    uploaded_at: datetime
    processed_at: datetime | None


class DocumentListResponse(BaseModel):
    documents: list[DocumentOut]


class DocumentStatusResponse(BaseModel):
    id: str
    status: str
    error_message: str | None
