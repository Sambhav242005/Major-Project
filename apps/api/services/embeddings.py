"""Embedding service — calls Ollama for real embeddings."""

import httpx
from core.config import settings


async def embed_text(text: str) -> list[float]:
    """Get embedding vector for text via Ollama."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/embed",
            json={"model": settings.OLLAMA_EMBEDDING_MODEL, "input": text},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["embeddings"][0]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Get embedding vectors for multiple texts via Ollama."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/embed",
            json={"model": settings.OLLAMA_EMBEDDING_MODEL, "input": texts},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["embeddings"]
