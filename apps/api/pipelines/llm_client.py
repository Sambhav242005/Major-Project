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


async def _chatgpt_completion_stream(
    messages: list[dict[str, str]],
    model: str | None,
    response_format: dict | None = None,
):
    """Use the documented ChatGPT plan route, with explicit completion checks."""
    from core.chatgpt_oauth import get_access_token

    inputs = [
        {**message, "role": "developer" if message["role"] == "system" else message["role"]}
        for message in messages
    ]
    if response_format and response_format.get("type") != "text":
        # Plan usage has a narrower request contract. Keep JSON requirements in
        # the prompt instead of forwarding Chat Completions-only parameters.
        instruction = "Return only a valid JSON object, without markdown fences or commentary."
        if response_format.get("type") == "json_schema":
            instruction += " Follow this JSON schema: " + json.dumps(response_format["json_schema"])
        inputs.append({"role": "developer", "content": instruction})
    body = {
        "model": model or settings.LLM_MODEL,
        "input": inputs,
        "store": False,
        "stream": True,
    }
    token = await get_access_token(settings.CHATGPT_CREDENTIALS_PATH)
    completed = False
    try:
        async with _get_client().stream(
            "POST",
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        ) as resp:
            if resp.status_code >= 400:
                # Error bodies may echo request data or credentials.
                raise RuntimeError(f"ChatGPT inference request failed (HTTP {resp.status_code}).")
            data_lines: list[str] = []
            async for line in resp.aiter_lines():
                if line:
                    if line.startswith("data:"):
                        data_lines.append(line[5:].lstrip(" "))
                    continue
                if not data_lines:
                    continue
                payload = "\n".join(data_lines)
                data_lines.clear()
                try:
                    event = json.loads(payload)
                except json.JSONDecodeError:
                    raise RuntimeError("ChatGPT inference returned an invalid stream event.") from None
                if not isinstance(event, dict):
                    raise RuntimeError("ChatGPT inference returned an invalid stream event.")
                event_type = event.get("type")
                if event_type in {"response.failed", "response.incomplete", "error"}:
                    raise RuntimeError(f"ChatGPT inference ended with {event_type}.")
                if event_type == "response.completed":
                    completed = True
                    break
                if event_type == "response.output_text.delta":
                    delta = event.get("delta")
                    if not isinstance(delta, str):
                        raise RuntimeError("ChatGPT inference returned an invalid text delta.")
                    yield delta
    except httpx.HTTPError:
        raise RuntimeError("ChatGPT inference connection failed; the answer is incomplete.") from None
    if not completed:
        raise RuntimeError("ChatGPT inference stream ended without response.completed.")


async def chat_completion(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.3,
    response_format: dict | None = None,
    max_tokens: int = 4096,
) -> str:
    if settings.LLM_PROVIDER == "chatgpt":
        return "".join([
            part async for part in _chatgpt_completion_stream(messages, model, response_format)
        ])
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
    if settings.LLM_PROVIDER == "chatgpt":
        async for part in _chatgpt_completion_stream(messages, model):
            yield part
        return
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
