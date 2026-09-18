from pydantic import BaseModel


class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    page_number: int | None
    text: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResult]
