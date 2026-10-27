"""Offline contract tests for ChatGPT plan inference and the legacy provider."""

import json
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from pipelines import llm_client


def sse(*events):
    return "".join(f"data: {json.dumps(event)}\n\n" for event in events)


@pytest.fixture
def setup_client(monkeypatch):
    token_reader = AsyncMock(return_value="oauth-test-token")
    monkeypatch.setitem(sys.modules, "core.chatgpt_oauth", SimpleNamespace(get_access_token=token_reader))
    monkeypatch.setattr(llm_client.settings, "LLM_PROVIDER", "chatgpt")
    monkeypatch.setattr(llm_client.settings, "CHATGPT_CREDENTIALS_PATH", "/private/akgb.json")
    monkeypatch.setattr(llm_client.settings, "LLM_API_KEY", "must-not-use-this-key")
    monkeypatch.setattr(llm_client.settings, "LLM_BASE_URL", "https://untrusted.invalid/v1")
    monkeypatch.setattr(llm_client.settings, "LLM_MODEL", "account-model")
    return token_reader


@pytest.mark.asyncio
async def test_collects_responses_and_sends_only_supported_fields(setup_client, monkeypatch):
    messages = [{"role": "system", "content": "Be precise."}, {"role": "user", "content": "Hello"}]
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, text=sse(
            {"type": "response.created"},
            {"type": "response.output_text.delta", "delta": "Hello"},
            {"type": "response.reasoning_text.delta", "delta": "private reasoning"},
            {"type": "response.output_text.delta", "delta": " world"},
            {"type": "response.completed"},
        ))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        monkeypatch.setattr(llm_client, "_get_client", lambda: client)
        result = await llm_client.chat_completion(messages, temperature=0.9, max_tokens=3)
    assert result == "Hello world"
    assert str(requests[0].url) == "https://api.openai.com/v1/responses"
    assert requests[0].headers["authorization"] == "Bearer oauth-test-token"
    assert json.loads(requests[0].content) == {
        "model": "account-model", "store": False, "stream": True,
        "input": [{"role": "developer", "content": "Be precise."}, messages[1]],
    }
    assert messages[0]["role"] == "system"
    setup_client.assert_awaited_once_with("/private/akgb.json")


@pytest.mark.asyncio
async def test_json_requirement_is_prompted_without_chat_parameters(setup_client, monkeypatch):
    def handler(request):
        body = json.loads(request.content)
        assert body["model"] == "selected-account-model"
        assert body["input"][-1]["role"] == "developer"
        assert "valid JSON object" in body["input"][-1]["content"]
        assert "response_format" not in body
        return httpx.Response(200, text=sse(
            {"type": "response.output_text.delta", "delta": '{"ok": true}'},
            {"type": "response.completed"},
        ))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        monkeypatch.setattr(llm_client, "_get_client", lambda: client)
        result = await llm_client.chat_completion(
            [{"role": "user", "content": "Return JSON"}],
            model="selected-account-model", response_format={"type": "json_object"},
        )
    assert json.loads(result) == {"ok": True}


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal", ["response.failed", "response.incomplete", "error", None])
async def test_partial_answer_does_not_hide_failure(setup_client, monkeypatch, terminal):
    events = [{"type": "response.output_text.delta", "delta": "partial"}]
    if terminal:
        events.append({"type": terminal, "error": {"message": "sensitive-provider-detail"}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, text=sse(*events))
    )) as client:
        monkeypatch.setattr(llm_client, "_get_client", lambda: client)
        parts = llm_client.chat_completion_stream([{"role": "user", "content": "Hi"}])
        assert await anext(parts) == "partial"
        with pytest.raises(RuntimeError) as error:
            await anext(parts)
    assert "sensitive-provider-detail" not in str(error.value)
    assert (terminal or "without response.completed") in str(error.value)


@pytest.mark.asyncio
async def test_nonstream_request_discards_partial_failure(setup_client, monkeypatch):
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, text=sse(
            {"type": "response.output_text.delta", "delta": "partial"},
            {"type": "response.failed"},
        ))
    )) as client:
        monkeypatch.setattr(llm_client, "_get_client", lambda: client)
        with pytest.raises(RuntimeError, match="response.failed"):
            await llm_client.chat_completion([{"role": "user", "content": "Hi"}])


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal", ["response.failed", "response.incomplete", None])
async def test_application_chat_failure_never_emits_completion(setup_client, monkeypatch, terminal):
    from services.chat import streaming
    from services import webhooks

    monkeypatch.setattr(streaming, "query_chunks", AsyncMock(return_value=[]))
    monkeypatch.setattr(streaming, "_get_entity_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(streaming, "_expand_via_graph", AsyncMock(return_value=[]))
    audit = AsyncMock()
    webhook = AsyncMock()
    monkeypatch.setattr(streaming, "write_audit_log", audit)
    monkeypatch.setattr(webhooks, "fire_event", webhook)
    db = MagicMock()
    db.flush = AsyncMock()
    db.rollback = AsyncMock()
    db.commit = AsyncMock()
    history = MagicMock()
    history.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=history)
    provider_events = [{"type": "response.output_text.delta", "delta": "partial answer"}]
    if terminal:
        provider_events.append({"type": terminal})
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, text=sse(*provider_events))
    )) as client:
        monkeypatch.setattr(llm_client, "_get_client", lambda: client)
        events = [event async for event in streaming.send_message(
            db, "550e8400-e29b-41d4-a716-446655440002", "Hello",
            "550e8400-e29b-41d4-a716-446655440001", "550e8400-e29b-41d4-a716-446655440000",
        )]
    assert [event["type"] for event in events] == ["generation", "chunk", "error"]
    assert events[1]["content"] == "partial answer"
    # The attempted generation is announced up front; the failure still never
    # completes, persists or announces the answer.
    from core.config import settings as app_settings
    assert events[0] == {
        "type": "generation",
        "provider": "configured",
        "model": app_settings.LLM_CHAT_MODEL,
    }
    assert "could not be completed" in events[-1]["error"]
    assert [call.args[0].role for call in db.add.call_args_list] == ["user"]
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()
    audit.assert_not_awaited()
    webhook.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", ["data: not-json\n\n", "data: []\n\n", "data: [DONE]\n\n"])
async def test_invalid_or_legacy_event_is_rejected(setup_client, monkeypatch, stream):
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, text=stream)
    )) as client:
        monkeypatch.setattr(llm_client, "_get_client", lambda: client)
        with pytest.raises(RuntimeError, match="invalid stream event"):
            await llm_client.chat_completion([{"role": "user", "content": "Hi"}])


@pytest.mark.asyncio
async def test_http_failure_is_redacted(setup_client, monkeypatch):
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(401, text="oauth-test-token secret")
    )) as client:
        monkeypatch.setattr(llm_client, "_get_client", lambda: client)
        with pytest.raises(RuntimeError, match="HTTP 401") as error:
            await llm_client.chat_completion([{"role": "user", "content": "Hi"}])
    assert "secret" not in str(error.value)
    assert "oauth-test-token" not in str(error.value)


@pytest.mark.asyncio
async def test_network_failure_is_redacted(setup_client, monkeypatch):
    def handler(request):
        raise httpx.ReadError("sensitive network detail")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        monkeypatch.setattr(llm_client, "_get_client", lambda: client)
        with pytest.raises(RuntimeError, match="connection failed") as error:
            await llm_client.chat_completion([{"role": "user", "content": "Hi"}])
    assert "sensitive" not in str(error.value)


@pytest.mark.asyncio
async def test_multiline_sse_and_fresh_token_for_each_call(setup_client, monkeypatch):
    setup_client.side_effect = ["first-token", "renewed-token"]
    tokens = []

    def handler(request):
        tokens.append(request.headers["authorization"])
        return httpx.Response(200, text=(
            ': keepalive\n\nevent: response.output_text.delta\n'
            'data: {"type": "response.output_text.delta",\n'
            'data: "delta": "hello"}\n\n'
            'data: {"type": "response.completed"}\n\n'
        ))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        monkeypatch.setattr(llm_client, "_get_client", lambda: client)
        for _ in range(2):
            assert [part async for part in llm_client.chat_completion_stream([])] == ["hello"]
    assert tokens == ["Bearer first-token", "Bearer renewed-token"]
    assert setup_client.await_count == 2


@pytest.mark.asyncio
async def test_transport_interruption_after_partial_is_failure(setup_client, monkeypatch):
    class InterruptedStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield sse({"type": "response.output_text.delta", "delta": "partial"}).encode()
            raise httpx.ReadError("private transport detail")

    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, stream=InterruptedStream())
    )) as client:
        monkeypatch.setattr(llm_client, "_get_client", lambda: client)
        parts = llm_client.chat_completion_stream([])
        assert await anext(parts) == "partial"
        with pytest.raises(RuntimeError, match="answer is incomplete"):
            await anext(parts)


@pytest.mark.asyncio
async def test_legacy_provider_preserves_request_contract(setup_client, monkeypatch):
    monkeypatch.setattr(llm_client.settings, "LLM_PROVIDER", "openai")
    messages = [{"role": "system", "content": "Original system role"}]

    def handler(request):
        assert str(request.url) == "https://untrusted.invalid/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer must-not-use-this-key"
        assert json.loads(request.content) == {
            "model": "legacy-model", "messages": messages, "temperature": 0.7,
            "max_tokens": 20, "response_format": {"type": "json_object"},
        }
        return httpx.Response(200, json={"choices": [{"message": {"content": "legacy"}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        monkeypatch.setattr(llm_client, "_get_client", lambda: client)
        assert await llm_client.chat_completion(
            messages, model="legacy-model", temperature=0.7,
            max_tokens=20, response_format={"type": "json_object"},
        ) == "legacy"
    setup_client.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_stream_remains_chat_completions(setup_client, monkeypatch):
    monkeypatch.setattr(llm_client.settings, "LLM_PROVIDER", "openai")

    def handler(request):
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(200, text=(
            'data: {"choices":[{"delta":{"content":"legacy stream"}}]}\n\n'
            "data: [DONE]\n\n"
        ))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        monkeypatch.setattr(llm_client, "_get_client", lambda: client)
        assert [part async for part in llm_client.chat_completion_stream([])] == ["legacy stream"]
    setup_client.assert_not_awaited()
