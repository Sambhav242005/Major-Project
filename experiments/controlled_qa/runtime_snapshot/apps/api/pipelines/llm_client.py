"""OpenAI-compatible LLM client — works with Groq, Ollama, OpenAI, etc."""

import json
import logging
from typing import Any

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

_http_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=120.0)
    return _http_client


def _get_auth_header() -> dict[str, str]:
    if settings.LLM_API_KEY:
        return {"Authorization": f"Bearer {settings.LLM_API_KEY}"}
    return {}


async def chat_completion(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.3,
    response_format: dict | None = None,
    max_tokens: int = 4096,
) -> str:
    client = _get_client()
    body: dict[str, Any] = {
        "model": model or settings.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        body["response_format"] = response_format

    resp = await client.post(
        f"{settings.LLM_BASE_URL}/chat/completions",
        headers=_get_auth_header(),
        json=body,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


async def chat_completion_stream(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.3,
):
    client = _get_client()
    body = {
        "model": model or settings.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }

    async with client.stream(
        "POST",
        f"{settings.LLM_BASE_URL}/chat/completions",
        headers=_get_auth_header(),
        json=body,
    ) as resp:
        resp.raise_for_status()
        thinking = ""  # buffer for <think>...</think> blocks
        in_think = False
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload.strip() == "[DONE]":
                break
            chunk = json.loads(payload)
            delta = chunk["choices"][0].get("delta", {})
            content = delta.get("content")
            if not content:
                continue
            # Strip reasoning blocks (<think>...</think>) so only the final
            # answer reaches the UI.
            while content:
                if in_think:
                    end = content.find("</think>")
                    if end == -1:
                        thinking += content
                        content = ""
                    else:
                        thinking += content[:end]
                        content = content[end + len("</think>"):]
                        in_think = False
                else:
                    start = content.find("<think>")
                    if start == -1:
                        yield content
                        content = ""
                    else:
                        if start > 0:
                            yield content[:start]
                        content = content[start + len("<think>"):]
                        in_think = True
