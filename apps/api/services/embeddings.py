"""Embedding service — OpenAI-compatible API."""

import httpx
from core.config import settings


async def embed_text(text: str) -> list[float]:
    """Get embedding vector for text."""
    headers = {}
    if settings.EMBEDDING_API_KEY:
        headers["Authorization"] = f"Bearer {settings.EMBEDDING_API_KEY}"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.EMBEDDING_BASE_URL}/embeddings",
            headers=headers,
            json={"model": settings.EMBEDDING_MODEL, "input": text},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["data"][0]["embedding"]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Get embedding vectors for multiple texts."""
    headers = {}
    if settings.EMBEDDING_API_KEY:
        headers["Authorization"] = f"Bearer {settings.EMBEDDING_API_KEY}"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.EMBEDDING_BASE_URL}/embeddings",
            headers=headers,
            json={"model": settings.EMBEDDING_MODEL, "input": texts},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return [item["embedding"] for item in data["data"]]
