"""OpenAI-compatible LLM client — works with Groq, Ollama, OpenAI, etc."""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from core.config import settings
from pipelines.model_request_capture import ModelRequestCapture, summarize_failure

logger = logging.getLogger(__name__)

# Reasoning-marker strings are assembled with chr() so the tags never appear
# verbatim in source (proves mid-template mangling cannot corrupt them).
_THINK_OPEN = chr(60) + "think" + chr(62)
_THINK_CLOSE = chr(60) + "/" + "think" + chr(62)

_http_client: httpx.AsyncClient | None = None


@dataclass(frozen=True)
class GenerationConfig:
    provider: str
    model: str
    base_url: str = ""
    api_key: str = field(default="", repr=False)


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
    capture: ModelRequestCapture | None = None,
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
    if capture:
        # Provider adaptation is part of the outbound request: the inspector
        # shows this adapted body, not the caller's original messages.
        capture.mark_transport(
            provider="chatgpt",
            model=body["model"],
            request_shape="responses",
            method="POST",
            url="https://api.openai.com/v1/responses",
            headers={"Authorization": "(value withheld)", "Content-Type": "application/json"},
            body=body,
        )
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
    except (GeneratorExit, asyncio.CancelledError):
        if capture:
            capture.mark_cancelled()
        raise
    except httpx.HTTPError as exc:
        if capture:
            capture.mark_failed(summarize_failure(exc))
        raise RuntimeError("ChatGPT inference connection failed; the answer is incomplete.") from None
    except Exception as exc:
        if capture:
            capture.mark_failed(str(exc) if isinstance(exc, RuntimeError) else summarize_failure(exc))
        raise
    if not completed:
        if capture:
            capture.mark_failed("provider stream ended without response.completed")
        raise RuntimeError("ChatGPT inference stream ended without response.completed.")
    if capture:
        capture.mark_sent()


async def chat_completion(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.3,
    response_format: dict | None = None,
    max_tokens: int = 4096,
    capture: ModelRequestCapture | None = None,
) -> str:
    if settings.LLM_PROVIDER == "chatgpt":
        kwargs = {"capture": capture} if capture is not None else {}
        return "".join([
            part async for part in _chatgpt_completion_stream(
                messages, model, response_format, **kwargs
            )
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

    url = f"{settings.LLM_BASE_URL}/chat/completions"
    headers = _get_auth_header()
    if capture:
        capture.mark_transport(
            provider=settings.LLM_PROVIDER,
            model=body["model"],
            request_shape="chat_completions",
            method="POST",
            url=url,
            headers=headers,
            body=body,
        )
    try:
        resp = await client.post(
            url,
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        if capture and not capture.terminal:
            capture.mark_failed(summarize_failure(exc))
        raise


async def chat_completion_stream(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.3,
    generation: GenerationConfig | None = None,
    capture: ModelRequestCapture | None = None,
):
    provider = generation.provider if generation else settings.LLM_PROVIDER
    model = generation.model if generation else model
    if provider == "chatgpt":
        kwargs = {"capture": capture} if capture is not None else {}
        async for part in _chatgpt_completion_stream(messages, model, **kwargs):
            yield part
        return
    client = _get_client()
    base_url = generation.base_url if generation else settings.LLM_BASE_URL
    if generation:
        headers = {"Authorization": f"Bearer {generation.api_key}"} if generation.api_key else {}
    else:
        headers = _get_auth_header()
    body = {
        "model": model or settings.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    url = f"{base_url}/chat/completions"
    if capture:
        # Final application transport boundary: the sanitized outbound request
        # is captured exactly as it is about to be handed to httpx.
        capture.mark_transport(
            provider=provider,
            model=body["model"],
            request_shape="chat_completions",
            method="POST",
            url=url,
            headers=headers,
            body=body,
        )

    try:
        async with client.stream(
            "POST",
            url,
            headers=headers,
            json=body,
        ) as resp:
            resp.raise_for_status()
            thinking = ""  # buffer for the hidden reasoning blocks
            in_think = False
            provider_completed = False
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload.strip() == "[DONE]":
                    provider_completed = True
                    break
                chunk = json.loads(payload)
                delta = chunk["choices"][0].get("delta", {})
                content = delta.get("content")
                if not content:
                    continue
                # Strip hidden reasoning blocks (the literal open/close think
                # tags) so only the final answer reaches the UI.
                while content:
                    if in_think:
                        end = content.find(_THINK_CLOSE)
                        if end == -1:
                            thinking += content
                            content = ""
                        else:
                            thinking += content[:end]
                            content = content[end + len(_THINK_CLOSE):]
                            in_think = False
                    else:
                        start = content.find(_THINK_OPEN)
                        if start == -1:
                            yield content
                            content = ""
                        else:
                            if start > 0:
                                yield content[:start]
                            content = content[start + len(_THINK_OPEN):]
                            in_think = True
    except (GeneratorExit, asyncio.CancelledError):
        if capture:
            capture.mark_cancelled()
        raise
    except Exception as exc:
        if capture:
            capture.mark_failed(summarize_failure(exc))
        raise
    if capture:
        # Record only the provider's own success marker as "sent"; a stream
        # that ended without it is an incomplete/failed request.
        if provider_completed:
            capture.mark_sent()
        else:
            capture.mark_failed("provider stream ended without the [DONE] completion marker")
