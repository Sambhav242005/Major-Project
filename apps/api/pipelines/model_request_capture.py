"""Transport-boundary capture of outbound model requests.

Lives in ``pipelines`` so ``pipelines.llm_client`` can record the exact
sanitized payload it is about to hand to a provider without importing any
service (which would create an import cycle). ``services.chat.request_capture``
stores finished snapshots in a short-lived in-process TTL/LRU store.

Privacy rules (see TODO 2.24): snapshots never contain authorization headers,
API keys, OAuth tokens or signed-URL secrets. Binary/base64 attachment bodies
are withheld with metadata only. Token counts are estimates and are labeled as
such.
"""

import base64
import json
import time
from dataclasses import dataclass, field
from typing import Any

# Headers never recorded in snapshots. Their presence (name only) is kept so
# the inspector can honestly show that an excluded secret header was sent.
EXCLUDED_HEADERS = frozenset({
    "authorization", "proxy-authorization", "cookie", "x-api-key",
    "access-token", "refresh-token",
})

# JSON keys that must never be echoed verbatim in a snapshot.
SECRET_KEYS = frozenset({
    "api_key", "apikey", "authorization", "access_token", "refresh_token",
    "id_token", "cookie", "secret", "password", "signed_url",
})

# JSON keys whose values carry binary/base64 attachment payloads.
BINARY_KEYS = frozenset({"image_url", "input_audio", "file_data", "b64_json", "audio_data"})

_BASE64_RE = __import__("re").compile(r"^[A-Za-z0-9+/\-_.:;=,]*$")

TERMINAL_STATUSES = ("sent", "failed", "cancelled")


def estimate_tokens(text: str) -> int:
    """Rough chars/4 token estimate. Snapshots label this as an estimate."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def _redact_binary(value: Any) -> Any:
    """Describe binary attachment values without copying their bytes."""
    if not isinstance(value, str):
        return value
    mime = ""
    payload = value
    if value.startswith("data:"):
        header, _, payload = value.partition(",")
        mime = header[5:].partition(";")[0]
    byte_count = len(base64.b64decode(payload + "===" , validate=False)) if payload else 0
    return {
        "content": "(binary data withheld from snapshot)",
        "encoding": "data_uri" if mime else "base64",
        "mime_type": mime or "application/octet-stream",
        "bytes": byte_count,
        "characters_in_payload": len(value),
    }


def sanitize_payload(value: Any) -> Any:
    """Deep-copy a JSON-ready payload, excluding secrets and binary bodies.

    Strings are left untouched: chat prompt text is the payload's reason for
    existing and the snapshot must show it exactly as sent. Only credential
    keys and known binary attachment containers are modified.
    """
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_lower = str(key).lower()
            if key_lower in SECRET_KEYS:
                result[str(key)] = "(excluded from snapshot)"
                continue
            if key_lower in BINARY_KEYS:
                result[str(key)] = _redact_binary(item)
                continue
            result[str(key)] = sanitize_payload(item)
        return result
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_payload(item) for item in value]
    return value


def sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    """Keep non-secret header values; blank out excluded header values."""
    sanitized: dict[str, str] = {}
    for name, value in (headers or {}).items():
        if str(name).lower() in EXCLUDED_HEADERS or any(
            token in str(name).lower() for token in ("token", "secret", "key")
        ):
            sanitized[str(name)] = "(excluded from snapshot)"
            continue
        sanitized[str(name)] = value
    return sanitized


def summarize_failure(exc: BaseException) -> str:
    """Provider-safe failure annotations for snapshot ``failure_reason``."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if isinstance(status, int):
        return f"provider returned HTTP {status}"
    if isinstance(exc, (GeneratorExit, __import__("asyncio").CancelledError)):
        return "client stopped before generation completed"
    if exc.__class__.__module__.startswith("httpx"):
        return "provider connection failed"
    return "generation request failed"


@dataclass
class ModelRequestCapture:
    """Collects one outbound model request for the chat inspector.

    ``streaming.py`` creates the instance (with application-side assembly
    metadata), ``pipelines.llm_client`` records the provider-adapted transport
    payload at the final application boundary, then marks exactly one terminal
    status: ``sent``, ``failed`` or ``cancelled``.
    """

    request_id: str
    assembly: dict[str, Any] = field(default_factory=dict)

    request_shape: str = "chat_completions"
    provider: str = ""
    model: str = ""
    endpoint: str = ""
    transport: dict[str, Any] | None = None
    generation_settings: dict[str, Any] | None = None
    status: str | None = None
    failure_reason: str | None = None
    sent_at: str | None = None

    # --- recorded by pipelines.llm_client at the transport boundary ---
    def mark_transport(
        self,
        *,
        provider: str,
        model: str,
        request_shape: str,
        method: str,
        url: str,
        headers: dict[str, str],
        body: dict[str, Any],
    ) -> None:
        self.provider = provider
        self.model = model
        self.request_shape = request_shape
        self.endpoint = url
        self.transport = {
            "method": method,
            "url": url,
            "headers": sanitize_headers(headers),
            "body": sanitize_payload(body),
        }
        self.generation_settings = {
            key: sanitize_payload(value) if not isinstance(value, (str, int, float, bool)) and value is not None else value
            for key, value in (
                ("stream", body.get("stream")),
                ("temperature", body.get("temperature")),
                ("max_tokens", body.get("max_tokens")),
                ("response_format", body.get("response_format")),
            )
            if key in body
        }
        if body.get("response_format"):
            # ChatGPT /v1/responses adapts response_format into a developer
            # instruction; keep the adapted marker next to the shape.
            pass
        self.sent_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # --- terminal statuses (first terminal write wins) ---
    def _set_terminal(self, status: str, reason: str | None = None) -> None:
        if self.status in TERMINAL_STATUSES:
            return
        self.status = status
        self.failure_reason = reason

    def mark_sent(self) -> None:
        self._set_terminal("sent")

    def mark_failed(self, reason: str | None = None) -> None:
        self._set_terminal("failed", reason or "generation request failed")

    def mark_cancelled(self) -> None:
        self._set_terminal("cancelled", "client stopped before generation completed")

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    # --- snapshot ---
    def snapshot(self) -> dict[str, Any]:
        messages = (self.transport or {}).get("body", {}).get("messages")
        if messages is None:
            input_list = (self.transport or {}).get("body", {}).get("input")
            if input_list is not None:
                messages = input_list
        per_message = [
            {
                "role": message.get("role", "unknown"),
                "estimated_tokens": estimate_tokens(json.dumps(message, default=str)),
            }
            if isinstance(message, dict)
            else {"estimated_tokens": estimate_tokens(json.dumps(message, default=str))}
            for message in (messages or [])
        ]
        total = sum(item["estimated_tokens"] for item in per_message)
        body_chars = len(json.dumps((self.transport or {}).get("body", {}), default=str))
        return {
            "schema": "model_request.snapshot.v1",
            "request_id": self.request_id,
            "status": self.status,
            "failure_reason": self.failure_reason,
            "captured_at": self.sent_at,
            "provider": {
                "provider": self.provider,
                "model": self.model,
                "endpoint": self.endpoint,
                "request_shape": self.request_shape,
            },
            "generation_settings": self.generation_settings or {},
            "request": self.transport,
            "token_counts": {
                "estimate": True,
                "method": "chars/4 over JSON-encoded message fields; provider tokens may differ",
                "total": total,
                "by_message": per_message,
                "request_body_characters": body_chars,
            },
            "assembly": self.assembly,
            "sanitization": {
                "authorization_headers": "(excluded from snapshot)",
                "api_keys": "(excluded from snapshot)",
                "hidden_reasoning": "(excluded from snapshot)",
                "binary_attachments": "(bodies withheld; metadata kept)",
                "excluded_header_names": sorted(EXCLUDED_HEADERS),
            },
            "retention": {
                "storage": "in-process TTL/LRU memory only; not persisted to the database",
                "view_is_read_only": True,
                "note": "snapshots disappear on restart or eviction",
            },
            "attachments": [],
            "tools": {"present": False},
        }

    def to_json(self, indent: str | None = None) -> str:
        return json.dumps(self.snapshot(), indent=indent, default=str)
