"""Embeddings package — re-exports original public API."""

from pipelines.embeddings.client import get_chroma_client
from pipelines.embeddings.embedding_function import (
    TASK_DOCUMENT,
    TASK_QUERY,
    EmbeddingError,
    GeminiEmbeddingFunction,
    OpenAICompatibleEmbeddingFunction,
    get_embedding_function,
    reset_embedding_function_cache,
)
from pipelines.embeddings.query import query_chunks
from pipelines.embeddings.store import (
    EmbeddingSpaceMismatchError,
    delete_document_chunks,
    get_collection,
    upsert_chunks,
)

__all__ = [
    "OpenAICompatibleEmbeddingFunction",
    "GeminiEmbeddingFunction",
    "EmbeddingError",
    "EmbeddingSpaceMismatchError",
    "TASK_DOCUMENT",
    "TASK_QUERY",
    "get_chroma_client",
    "get_embedding_function",
    "reset_embedding_function_cache",
    "get_collection",
    "upsert_chunks",
    "query_chunks",
    "delete_document_chunks",
]