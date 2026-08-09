"""Provider-agnostic LLM client — OpenAI primary, Ollama fallback."""

import json
import logging
from typing import Any

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

# Reusable async client
_http_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=120.0)
    return _http_client


def _get_provider() -> str:
    """Determine which LLM provider to use."""
    if settings.LLM_PROVIDER == "ollama" or not settings.OPENAI_API_KEY:
        if settings.OLLAMA_BASE_URL:
            return "ollama"
    return "openai"


async def chat_completion(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.3,
    response_format: dict | None = None,
    max_tokens: int = 4096,
) -> str:
    """Send chat completion request to active LLM provider.

    Args:
        messages: List of {"role": "system"|"user"|"assistant", "content": "..."}
        model: Override model (defaults to config)
        temperature: Sampling temperature
        response_format: Optional {"type": "json_object"} for structured output (OpenAI only)
        max_tokens: Max response tokens

    Returns:
        Assistant message content string.
    """
    provider = _get_provider()

    if provider == "ollama":
        # Ollama does not support response_format — strip it
        return await _ollama_completion(messages, model, temperature)
    else:
        return await _openai_completion(messages, model, temperature, response_format, max_tokens)


async def chat_completion_stream(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.3,
):
    """Stream chat completion tokens. Yields content strings."""
    provider = _get_provider()

    if provider == "ollama":
        async for chunk in _ollama_stream(messages, model, temperature):
            yield chunk
    else:
        async for chunk in _openai_stream(messages, model, temperature):
            yield chunk


async def _openai_completion(
    messages: list[dict[str, str]],
    model: str | None,
    temperature: float,
    response_format: dict | None,
    max_tokens: int,
) -> str:
    client = _get_client()
    body: dict[str, Any] = {
        "model": model or settings.OPENAI_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        body["response_format"] = response_format

    resp = await client.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
        json=body,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


async def _openai_stream(
    messages: list[dict[str, str]],
    model: str | None,
    temperature: float,
):
    client = _get_client()
    body = {
        "model": model or settings.OPENAI_MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }

    async with client.stream(
        "POST",
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
        json=body,
    ) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload.strip() == "[DONE]":
                break
            chunk = json.loads(payload)
            delta = chunk["choices"][0].get("delta", {})
            if "content" in delta:
                yield delta["content"]


async def _ollama_completion(
    messages: list[dict[str, str]],
    model: str | None,
    temperature: float,
) -> str:
    client = _get_client()
    body = {
        "model": model or settings.OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }

    resp = await client.post(f"{settings.OLLAMA_BASE_URL}/api/chat", json=body)
    resp.raise_for_status()
    data = resp.json()
    return data["message"]["content"]


async def _ollama_stream(
    messages: list[dict[str, str]],
    model: str | None,
    temperature: float,
):
    client = _get_client()
    body = {
        "model": model or settings.OLLAMA_MODEL,
        "messages": messages,
        "stream": True,
        "options": {"temperature": temperature},
    }

    async with client.stream("POST", f"{settings.OLLAMA_BASE_URL}/api/chat", json=body) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line.strip():
                continue
            chunk = json.loads(line)
            if "message" in chunk and "content" in chunk["message"]:
                yield chunk["message"]["content"]
