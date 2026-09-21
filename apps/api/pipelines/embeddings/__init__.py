"""Embeddings package — re-exports original public API."""

from pipelines.embeddings.client import get_chroma_client
from pipelines.embeddings.embedding_function import (
    OpenAICompatibleEmbeddingFunction,
    get_embedding_function,
)
from pipelines.embeddings.query import query_chunks
from pipelines.embeddings.store import delete_document_chunks, get_collection, upsert_chunks

__all__ = [
    "OpenAICompatibleEmbeddingFunction",
    "get_chroma_client",
    "get_embedding_function",
    "get_collection",
    "upsert_chunks",
    "query_chunks",
    "delete_document_chunks",
]
