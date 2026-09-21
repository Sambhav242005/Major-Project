"""Embedding function using OpenAI-compatible API."""

import chromadb
from core.config import settings


class OpenAICompatibleEmbeddingFunction(chromadb.EmbeddingFunction):
    """Embedding function using OpenAI-compatible API (Ollama, Groq, etc.)."""

    def __call__(self, input: chromadb.Documents) -> chromadb.Embeddings:
        import httpx

        url = f"{settings.EMBEDDING_BASE_URL}/embeddings"
        headers = {}
        if settings.EMBEDDING_API_KEY:
            headers["Authorization"] = f"Bearer {settings.EMBEDDING_API_KEY}"

        with httpx.Client(timeout=60) as client:
            resp = client.post(url, headers=headers, json={
                "model": settings.EMBEDDING_MODEL,
                "input": input,
            })
            resp.raise_for_status()
            data = resp.json()
            return [item["embedding"] for item in data["data"]]


_embedding_fn = None


def get_embedding_function():
    global _embedding_fn
    if _embedding_fn is None:
        try:
            _embedding_fn = OpenAICompatibleEmbeddingFunction()
        except Exception:
            _embedding_fn = None
    return _embedding_fn
