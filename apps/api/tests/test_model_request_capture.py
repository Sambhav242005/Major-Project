"""Transport-level tests for the model request inspector (TODO 2.24, Phase 1).

Every outbound chat request is captured at the final application transport
boundary (``pipelines.llm_client``) and compared against the wire request the
provider actually received. Authorization, API keys and provider tokens must
never appear in a snapshot; captures must reflect failures and cancellations
accurately; and only the owning project (through an existing chat session) may
read a snapshot back.
"""

import json
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

from core.config import settings
from pipelines import llm_client
from services.chat import streaming
from services.chat import request_capture as store

PROJECT_UUID = "550e8400-e29b-41d4-a716-446655440001"
SESSION_UUID = "550e8400-e29b-41d4-a716-446655440002"
OTHER_PROJECT_UUID = "99999999-9999-9999-9999-999999999999"


def legacy_sse(*texts):
    events = [{"choices": [{"delta": {"content": text}}]} for text in texts]
    return "".join(f"data: {json.dumps(event)}\n\n" for event in events) + "data: [DONE]\n\n"


def wire_body(request: httpx.Request) -> dict:
    return json.loads(request.content)


@pytest.fixture(autouse=True)
def clean_store():
    store.clear_store()
    yield
    store.clear_store()


def streaming_client(httpx_handler, monkeypatch):
    client = httpx.AsyncClient(transport=httpx.MockTransport(httpx_handler))
    monkeypatch.setattr(llm_client, "_get_client", lambda: client)
    return client


def make_db(history_rows=None):
    db = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    history_result = MagicMock()
    history_result.scalars.return_value.all.return_value = history_rows or []
    db.execute = AsyncMock(return_value=history_result)
    return db


@pytest.fixture
def chat_mocks(monkeypatch):
    """Stand up the chat pipeline without external services or a database."""
    monkeypatch.setattr(streaming, "query_chunks", AsyncMock(return_value=[]))
    monkeypatch.setattr(streaming, "_get_entity_context", AsyncMock(return_value=[]))
    monkeypatch.setattr(streaming, "_expand_via_graph", AsyncMock(return_value=[]))
    monkeypatch.setattr(streaming, "write_audit_log", AsyncMock())
    from services import webhooks

    monkeypatch.setattr(webhooks, "fire_event", AsyncMock())
    return make_db()


async def collect_events(db, **overrides):
    events = []
    async for event in streaming.send_message(
        db=db,
        session_id=SESSION_UUID,
        message=overrides.pop("message", "Hello"),
        project_id=overrides.pop("project_id", PROJECT_UUID),
        actor_id="550e8400-e29b-41d4-a716-446655440000",
        **overrides,
    ):
        events.append(event)
    return events


def make_session_db():
    """Dict-returning DB for get_session(): found session + no messages."""
    db = MagicMock()
    session_result = MagicMock()
    session_result.scalar_one_or_none.return_value = MagicMock()
    messages_result = MagicMock()
    messages_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(side_effect=[session_result, messages_result])
    return db


# --- llm_client: captured payload vs the wire request ---

@pytest.mark.asyncio
async def test_transport_snapshot_matches_outbound_request(monkeypatch):
    wire_requests = []

    def handler(request):
        wire_requests.append(request)
        return httpx.Response(200, text=legacy_sse("Hello"))

    streaming_client(handler, monkeypatch)
    config = llm_client.GenerationConfig(
        "openai", "selected-model", "https://api.groq.com/openai/v1", "secret-groq-key"
    )
    capture = llm_client.ModelRequestCapture(request_id="req-transport-match")
    assert "".join([
        part async for part in llm_client.chat_completion_stream(
            [{"role": "user", "content": "Hi"}],
            temperature=0.4,
            generation=config,
            capture=capture,
        )
    ]) == "Hello"

    snapshot = capture.snapshot()
    # The captured payload is exactly the JSON body the provider received.
    assert snapshot["request"]["body"] == wire_body(wire_requests[0])
    assert snapshot["request"]["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert snapshot["request"]["method"] == "POST"
    # Secrets are excluded but their presence stays visible.
    assert snapshot["request"]["headers"] == {"Authorization": "(excluded from snapshot)"}
    assert snapshot["provider"] == {
        "provider": "openai",
        "model": "selected-model",
        "endpoint": "https://api.groq.com/openai/v1/chat/completions",
        "request_shape": "chat_completions",
    }
    assert snapshot["status"] == "sent"
    assert snapshot["generation_settings"] == {"stream": True, "temperature": 0.4}
    dump = json.dumps(snapshot)
    assert "secret-groq-key" not in dump
    assert "Bearer" not in dump


@pytest.mark.asyncio
async def test_token_counts_are_labeled_estimates(monkeypatch):
    def handler(request):
        return httpx.Response(200, text=legacy_sse("ok"))

    streaming_client(handler, monkeypatch)
    capture = llm_client.ModelRequestCapture(request_id="req-tokens")
    messages = [
        {"role": "system", "content": "s" * 80},
        {"role": "user", "content": "u" * 40},
    ]
    parts = llm_client.chat_completion_stream(messages, capture=capture)
    assert [part async for part in parts] == ["ok"]

    token_counts = capture.snapshot()["token_counts"]
    assert token_counts["estimate"] is True
    assert "estimate" in token_counts["method"]
    assert token_counts["total"] >= 30
    assert [entry["role"] for entry in token_counts["by_message"]] == ["system", "user"]


@pytest.mark.asyncio
async def test_binary_attachment_bodies_are_withheld(monkeypatch):
    image_data = "data:image/png;base64,YWJjZGVmZ2hpamtsbW5vcA=="
    audio_b64 = "UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQ=="

    def handler(request):
        return httpx.Response(200, text=legacy_sse("ok"))

    streaming_client(handler, monkeypatch)
    capture = llm_client.ModelRequestCapture(request_id="req-binary")
    body_messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": "What is in this image?"},
            {"type": "image_url", "image_url": {"url": image_data}},
            {"type": "input_audio", "input_audio": {"data": audio_b64, "format": "wav"}},
        ],
    }]
    parts = llm_client.chat_completion_stream(body_messages, capture=capture)
    assert [part async for part in parts] == ["ok"]

    dump = json.dumps(capture.snapshot())
    assert "YWJjZGVmZ2hpamts" not in dump
    assert "UklGRiQ" not in dump
    assert "binary data withheld" in dump
    # The text part survives verbatim.
    assert "What is in this image?" in dump
    # The audio format metadata is still described.
    assert '"format": "wav"' in dump


@pytest.mark.asyncio
async def test_each_outbound_request_is_captured_separately(monkeypatch):
    wire_requests = []

    def handler(request):
        wire_requests.append(request)
        return httpx.Response(200, text=legacy_sse("ok"))

    streaming_client(handler, monkeypatch)
    snapshots = []
    for index in range(2):
        capture = llm_client.ModelRequestCapture(request_id=f"req-{index}")
        parts = llm_client.chat_completion_stream(
            [{"role": "user", "content": f"question {index}"}], capture=capture,
        )
        assert [part async for part in parts] == ["ok"]
        snapshots.append(capture.snapshot())

    assert snapshots[0]["request_id"] != snapshots[1]["request_id"]
    assert snapshots[0]["request"]["body"] == wire_body(wire_requests[0])
    assert snapshots[1]["request"]["body"] == wire_body(wire_requests[1])
    assert snapshots[0]["request"]["body"]["messages"][0]["content"] == "question 0"


@pytest.mark.asyncio
async def test_chatgpt_provider_adaptation_is_recorded(monkeypatch):
    token_reader = AsyncMock(return_value="oauth-test-token")
    monkeypatch.setitem(sys.modules, "core.chatgpt_oauth",
                        SimpleNamespace(get_access_token=token_reader))
    monkeypatch.setattr(llm_client.settings, "LLM_PROVIDER", "chatgpt")
    monkeypatch.setattr(llm_client.settings, "CHATGPT_CREDENTIALS_PATH", "/private/creds")
    monkeypatch.setattr(llm_client.settings, "LLM_API_KEY", "unused-server-key")

    wire_requests = []

    def handler(request):
        wire_requests.append(request)
        events = (
            {"type": "response.output_text.delta", "delta": "hey"},
            {"type": "response.reasoning_text.delta", "delta": "secret reasoning"},
            {"type": "response.completed"},
        )
        return httpx.Response(200, text="".join(f"data: {json.dumps(e)}\n\n" for e in events))

    streaming_client(handler, monkeypatch)
    capture = llm_client.ModelRequestCapture(request_id="req-chatgpt")
    assert "".join([
        part async for part in llm_client.chat_completion_stream(
            [{"role": "system", "content": "Be exact."}, {"role": "user", "content": "Hi"}],
            capture=capture,
        )
    ]) == "hey"

    snapshot = capture.snapshot()
    assert snapshot["provider"]["request_shape"] == "responses"
    assert snapshot["provider"]["endpoint"] == "https://api.openai.com/v1/responses"
    # Captured (sanitized) body equals the provider-adapted outbound body.
    assert snapshot["request"]["body"] == wire_body(wire_requests[0])
    adapted = snapshot["request"]["body"]["input"]
    assert [item["role"] for item in adapted] == ["developer", "user"]
    assert adapted[0]["content"] == "Be exact."
    dump = json.dumps(snapshot)
    assert "oauth-test-token" not in dump        # OAuth token excluded
    assert "secret reasoning" not in dump        # hidden reasoning excluded
    assert "unused-server-key" not in dump       # server API key excluded
    assert snapshot["status"] == "sent"


# --- full application flow through the transport boundary ---

@pytest.mark.asyncio
async def test_full_flow_capture_matches_wire_and_records_truncation(chat_mocks, monkeypatch):
    wire_requests = []

    def handler(request):
        wire_requests.append(request)
        return httpx.Response(200, text=legacy_sse("An answer"))

    streaming_client(handler, monkeypatch)

    long_text = "x" * 405 + "KEPT-HEAD:" + "x" * 395 + "DROPPED-TAIL-"
    monkeypatch.setattr(streaming, "query_chunks", AsyncMock(return_value=[{
        "chunk_id": "doc1_chunk_0", "document_id": "doc-uuid-1", "page_number": 3,
        "text": long_text, "score": 0.42, "filename": "report.pdf",
    }]))
    monkeypatch.setattr(streaming, "_get_entity_context", AsyncMock(return_value=[
        {"id": "ent-1", "name": "Northwind", "type": "org", "description": "A supplier"},
    ]))
    monkeypatch.setattr(streaming, "_expand_via_graph", AsyncMock(return_value=[
        {"id": "ent-2", "name": "Logistics", "type": "concept", "description": "Shipments"},
    ]))

    history_rows = [
        MagicMock(role="assistant", content="y" * 250),
        MagicMock(role="user", content="Earlier question"),
        # The just-added current user message arrives last; send_message's
        # history[:-1] slice excludes it.
        MagicMock(role="user", content="Summarize the report"),
    ]
    db = make_db(history_rows)

    events = await collect_events(db, message="Summarize the report")

    assert [e["type"] for e in events] == ["generation", "chunk", "citations", "done"]
    request_id = events[-1]["request_id"]
    assert request_id
    assert len(wire_requests) == 1

    request_db = make_session_db()
    snapshot = await store.get_snapshot_for_project(
        request_db, request_id, PROJECT_UUID,
    )
    assert snapshot is not None
    assert snapshot["request_id"] == request_id
    assert snapshot["status"] == "sent"
    assert snapshot["project_id"] == PROJECT_UUID
    assert snapshot["session_id"] == SESSION_UUID

    # Captured payload equals the outbound wire request exactly.
    assert snapshot["request"]["body"] == wire_body(wire_requests[0])
    assert snapshot["provider"]["model"] == settings.LLM_CHAT_MODEL

    body = snapshot["request"]["body"]
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    user_prompt = body["messages"][1]["content"]

    # Included history: assistant reply clipped to 200 characters inside the
    # prompt, and the truncation decision recorded in the assembly metadata.
    assert "Assistant: " + ("y" * 200) in user_prompt
    assert "y" * 250 not in user_prompt
    history_meta = snapshot["assembly"]["history"]
    assert history_meta["assistant_clipped_to_chars"] == 200
    assert history_meta["may_exclude_older_messages"] is False
    assert [(e["role"], e["truncated"]) for e in history_meta["entries"]] == [
        ("assistant", True), ("user", False),
    ]
    assert history_meta["entries"][1]["content"] == "Earlier question"

    # The retrieved source kept only its first 800 characters; the assembly
    # records the truncation and the prompt holds the retained text.
    source_meta = snapshot["assembly"]["retrieval"]["sources"][0]
    assert source_meta["truncated"] is True
    assert source_meta["original_characters"] == len(long_text)
    assert source_meta["filename"] == "report.pdf"
    assert source_meta["page_number"] == 3
    assert source_meta["chunk_id"] == "doc1_chunk_0"
    assert source_meta["text"] == long_text[:800]
    # Exactly 800 characters entered the prompt: the head marker is retained,
    # the tail marker beyond 800 characters never reaches the model.
    assert "KEPT-HEAD:" in user_prompt
    assert "DROPPED-TAIL-" not in user_prompt
    assert long_text[800:] not in user_prompt

    # Graph context appears in the prompt and is counted in the assembly.
    graph = snapshot["assembly"]["graph_context"]
    assert graph["entities_shown_in_prompt"] == 1
    assert graph["expanded_shown_in_prompt"] == 1
    assert graph["entities"][0]["name"] == "Northwind"
    assert "Northwind (org)" in user_prompt

    # Nothing else was sent: attachments and tools absent, stated explicitly.
    assert snapshot["attachments"] == []
    assert snapshot["tools"] == {"present": False}

    # Token counts are explicitly estimates.
    assert snapshot["token_counts"]["estimate"] is True
    assert snapshot["token_counts"]["total"] > 0

    # Sanitization: no secrets actually serialized anywhere in the snapshot.
    dump = json.dumps(snapshot)
    for forbidden in ('"Bearer', "Authorization: Bearer", '"api_key":', '"Authorization": "Bearer'):
        assert forbidden not in dump
    for name, value in snapshot["request"]["headers"].items():
        assert name.lower() in ("authorization", "content-type")
        if name.lower() == "authorization":
            assert value == "(excluded from snapshot)"


@pytest.mark.asyncio
async def test_failed_generation_recorded_and_readable(chat_mocks, monkeypatch):
    def handler(request):
        return httpx.Response(500, text="leaked provider detail")

    streaming_client(handler, monkeypatch)
    events = await collect_events(chat_mocks)
    assert [e["type"] for e in events] == ["generation", "error"]
    request_id = events[-1]["request_id"]
    assert request_id

    snapshot = await store.get_snapshot_for_project(
        make_session_db(), request_id, PROJECT_UUID,
    )
    assert snapshot is not None
    assert snapshot["status"] == "failed"
    assert snapshot["failure_reason"] == "provider returned HTTP 500"
    assert "leaked provider detail" not in json.dumps(snapshot)
    assert chat_mocks.rollback.await_count == 1


@pytest.mark.asyncio
async def test_cancelled_generation_recorded(chat_mocks, monkeypatch):
    def handler(request):
        return httpx.Response(200, text=legacy_sse("partial"))

    streaming_client(handler, monkeypatch)
    generator = streaming.send_message(
        db=chat_mocks,
        session_id=SESSION_UUID,
        message="Hello",
        project_id=PROJECT_UUID,
        actor_id="550e8400-e29b-41d4-a716-446655440000",
    )
    first = await generator.__anext__()
    assert first["type"] == "generation"
    first = await generator.__anext__()
    assert first["type"] == "chunk"
    # Closing the pipeline at the yield point must complete without raising;
    # the cancelled snapshot is registered during teardown.
    await generator.aclose()

    entries = [s for _, s in store._entries.values()]
    assert len(entries) == 1
    assert entries[0]["status"] == "cancelled"
    # A cancelled turn left no assistant answer in the database.
    chat_mocks.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_without_completion_marker_is_not_recorded_as_sent(chat_mocks, monkeypatch):
    def handler(request):
        # Legacy provider EOF without the [DONE] marker.
        return httpx.Response(200, text='data: {"choices":[{"delta":{"content":"partial"}}]}\n\n')

    streaming_client(handler, monkeypatch)
    events = await collect_events(chat_mocks)
    # Legacy semantics complete the turn, but the request record must not
    # claim "sent" — provider completion was never signaled.
    entries = [s for _, s in store._entries.values()]
    assert entries and entries[0]["status"] == "failed"
    assert "without the" in entries[0]["failure_reason"]


# --- retention and access control ---

def test_snapshot_excludes_url_credentials_and_signed_queries():
    capture = llm_client.ModelRequestCapture(request_id="url-privacy")
    capture.mark_transport(
        provider="openai", model="test", request_shape="chat_completions", method="POST",
        url="https://operator:gateway-secret@example.test/v1/chat/completions?api_key=query-secret#fragment-secret",
        headers={"Authorization": "Bearer header-secret"}, body={"messages": []},
    )
    snapshot = capture.snapshot()
    expected = "https://example.test/v1/chat/completions"
    assert snapshot["provider"]["endpoint"] == snapshot["request"]["url"] == expected
    assert "secret" not in json.dumps(snapshot)


async def test_media_evidence_times_survive_chat_citations(chat_mocks, monkeypatch):
    location = {"kind": "transcript", "start_seconds": 1.5, "end_seconds": 3.5,
                "model": "whisper", "machine_generated": True}
    monkeypatch.setattr(streaming, "query_chunks", AsyncMock(return_value=[{
        "text": "Project approved", "filename": "meeting.wav", "document_id": PROJECT_UUID,
        "chunk_id": "chunk", "source_location": location,
    }]))
    streaming_client(lambda request: httpx.Response(200, text=legacy_sse("Approved [1]")), monkeypatch)
    events = await collect_events(chat_mocks)
    citations = next(e["citations"] for e in events if e["type"] == "citations")
    assert citations[0]["source_location"] == location
    snapshot = list(store._entries.values())[0][1]
    assert "Time: 1.50-3.50s" in json.dumps(snapshot["request"]["body"])

@pytest.mark.asyncio
async def test_snapshot_expires_after_ttl():
    store.register_snapshot({"request_id": "req-ttl", "project_id": PROJECT_UUID,
                             "session_id": SESSION_UUID})
    db = MagicMock()
    db.execute = AsyncMock()

    # Foreign project refused before any database access.
    assert await store.get_snapshot_for_project(db, "req-ttl", OTHER_PROJECT_UUID) is None
    assert db.execute.await_count == 0

    # Expired entries are refused and purged from the store.
    request_id, (expires_at, snapshot) = next(iter(store._entries.items()))
    store._entries[request_id] = (store._now() - 1, snapshot)
    assert await store.get_snapshot_for_project(db, "req-ttl", PROJECT_UUID) is None
    assert request_id not in store._entries
    assert db.execute.await_count == 0


@pytest.mark.asyncio
async def test_store_evicts_beyond_capacity():
    for index in range(store.MAX_SNAPSHOTS + 5):
        store.register_snapshot({"request_id": f"req-{index}",
                                 "project_id": PROJECT_UUID, "session_id": SESSION_UUID})
    assert len(store._entries) == store.MAX_SNAPSHOTS
    assert "req-0" not in store._entries
    assert f"req-{store.MAX_SNAPSHOTS + 4}" in store._entries


@pytest.mark.asyncio
async def test_other_project_cannot_read_foreign_snapshot(chat_mocks, monkeypatch):
    def handler(request):
        return httpx.Response(200, text=legacy_sse("ok"))

    streaming_client(handler, monkeypatch)
    events = await collect_events(chat_mocks)
    request_id = events[-1]["request_id"]

    # Guard runs before any database access: a foreign project gets None and
    # must not trigger a single query.
    other_db = MagicMock()
    other_db.execute = AsyncMock()
    assert await store.get_snapshot_for_project(other_db, request_id, OTHER_PROJECT_UUID) is None
    assert other_db.execute.await_count == 0

    # The owning project can read it (session lookup succeeds).
    assert await store.get_snapshot_for_project(
        make_session_db(), request_id, PROJECT_UUID,
    ) is not None


@pytest.mark.asyncio
async def test_snapshot_requires_an_existing_session(chat_mocks, monkeypatch):
    def handler(request):
        return httpx.Response(200, text=legacy_sse("ok"))

    streaming_client(handler, monkeypatch)
    events = await collect_events(chat_mocks)
    request_id = events[-1]["request_id"]

    # Session deleted since the turn: the snapshot is unreadable even for the
    # same project id — chat membership is re-verified on every read.
    deleted_db = make_db()
    missing_result = MagicMock()
    missing_result.scalar_one_or_none.return_value = None
    deleted_db.execute = AsyncMock(return_value=missing_result)
    assert await store.get_snapshot_for_project(
        deleted_db, request_id, PROJECT_UUID,
    ) is None


# --- HTTP endpoint authorization ---

@pytest.fixture
def app_client(monkeypatch):
    from services.webhooks import dispatch, provisioning

    monkeypatch.setattr(provisioning, "ensure_inbound_webhook_secrets", AsyncMock(return_value=0))
    monkeypatch.setattr(dispatch, "run_retry_scheduler", AsyncMock())
    from app.factory import create_app
    from core.deps import get_project_id
    from core.security import get_current_user
    from db.session import get_db

    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "MOCK_AUTH", True)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: make_session_db()
    app.dependency_overrides[get_project_id] = lambda: PROJECT_UUID
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="550e8400-e29b-41d4-a716-446655440000", email="owner@example.com"
    )
    with TestClient(app) as client:
        yield client


def auth_headers() -> dict:
    return {"Authorization": "Bearer local-test"}


def test_endpoint_delivers_snapshot_to_own_project(app_client):
    store.register_snapshot({
        "request_id": "req-endpoint", "project_id": PROJECT_UUID,
        "session_id": SESSION_UUID, "status": "sent",
    })
    response = app_client.get("/chat/model-requests/req-endpoint", headers=auth_headers())
    assert response.status_code == 200
    assert response.json()["request_id"] == "req-endpoint"
    assert response.json()["status"] == "sent"


def test_endpoint_404_for_foreign_project_snapshot(app_client):
    store.register_snapshot({
        "request_id": "req-foreign", "project_id": OTHER_PROJECT_UUID,
        "session_id": SESSION_UUID, "status": "sent",
    })
    response = app_client.get("/chat/model-requests/req-foreign", headers=auth_headers())
    assert response.status_code == 404


def test_endpoint_404_for_unknown_or_expired_snapshot(app_client):
    response = app_client.get("/chat/model-requests/does-not-exist", headers=auth_headers())
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_endpoint_requires_authentication():
    from services.webhooks import dispatch, provisioning

    with __import__("unittest").mock.patch.object(
        provisioning, "ensure_inbound_webhook_secrets", AsyncMock(return_value=0),
    ), __import__("unittest").mock.patch.object(
        dispatch, "run_retry_scheduler", AsyncMock(),
    ):
        from app.factory import create_app

        with TestClient(create_app()) as client:
            response = client.get("/chat/model-requests/anything")
            assert response.status_code == 401
            assert response.json()["detail"] == "Missing or invalid Authorization header"
