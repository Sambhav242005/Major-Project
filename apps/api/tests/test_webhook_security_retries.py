"""Webhook signature, authorization and durable retry regressions (no network)."""
import asyncio
import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from db.models import InboundWebhook, WebhookDelivery, WebhookSubscription
from services.webhooks import dispatch, inbound
from services.webhooks.signing import verify_inbound_signature


@pytest.fixture
async def sessions():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        for table in [InboundWebhook.__table__, WebhookSubscription.__table__, WebhookDelivery.__table__]:
            await conn.run_sync(table.create)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


def signature(body, secret="test-secret"):
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.fixture
async def client(sessions, monkeypatch):
    from core.auth_middleware import GlobalAuthMiddleware
    from routers import webhooks
    app = FastAPI()
    app.add_middleware(GlobalAuthMiddleware)
    app.include_router(webhooks.router, prefix="/webhooks")
    async def db_override():
        async with sessions() as db:
            yield db
    app.dependency_overrides[webhooks.get_db] = db_override
    async with sessions() as db:
        db.add(InboundWebhook(id=uuid.uuid4(), project_id=uuid.uuid4(), name="test", slug="test", handler="trigger_agent", config={"secret": "test-secret"}, active=True))
        await db.commit()
    handler = AsyncMock(return_value={"status": "ok"})
    monkeypatch.setattr(inbound, "_handle_trigger_agent", handler)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as session:
        yield session, handler


@pytest.mark.parametrize("body,header,status", [
    (b'{}', None, 401), (b'{}', 'sha256=wrong', 401),
    (b'{"tampered":true}', signature(b'{}'), 401),
    (b'{}', signature(b'{}'), 200),
    (b'\xff', signature(b'\xff'), 400),
    (b'[]', signature(b'[]'), 400),
    (b'{}', 'sha256=\u00e9', 401),
])
async def test_inbound_signature_before_handler(client, body, header, status):
    session, handler = client
    headers = {"x-webhook-signature": header} if header and header.isascii() else {}
    response = await session.post("/webhooks/inbound/test", content=body, headers=headers)
    assert response.status_code == status
    assert handler.await_count == (1 if status == 200 else 0)


async def test_missing_secret_fails_closed(client, sessions):
    session, handler = client
    async with sessions() as db:
        from sqlalchemy import update
        await db.execute(update(InboundWebhook).values(config={}))
        await db.commit()
    response = await session.post("/webhooks/inbound/test", content=b'{}', headers={"x-webhook-signature": signature(b'{}')})
    assert response.status_code == 401
    handler.assert_not_awaited()


@pytest.mark.parametrize("method,path", [("GET", "/webhooks/inbound/test"), ("POST", "/webhooks/retry-pending"), ("POST", "/webhooks/subscriptions"), ("POST", "/webhooks/inbound/test/extra")])
async def test_only_single_inbound_post_is_public(client, method, path):
    session, _ = client
    assert (await session.request(method, path)).status_code == 401


async def test_retry_requires_editor():
    from routers.webhooks import retry_pending
    for member in [None, SimpleNamespace(role="viewer")]:
        result = MagicMock()
        result.scalar_one_or_none.return_value = member
        db = SimpleNamespace(execute=AsyncMock(return_value=result))
        with pytest.raises(HTTPException) as exc:
            await retry_pending(str(uuid.uuid4()), db, SimpleNamespace(id=str(uuid.uuid4())))
        assert exc.value.status_code == 403


async def add_delivery(db, project_id, *, due=True, active=True, attempts=0, success=False):
    sub = WebhookSubscription(id=uuid.uuid4(), project_id=project_id, event_type="test", url="https://example.com/hook", active=active)
    delivery = WebhookDelivery(id=uuid.uuid4(), subscription_id=sub.id, event_type="test", payload={"hello": "world"}, attempts=attempts, success=success, next_retry_at=datetime.now(timezone.utc) + timedelta(seconds=-1 if due else 3600))
    db.add_all([sub, delivery])
    await db.commit()
    return delivery


async def test_due_retries_project_isolation_and_backoff(sessions, monkeypatch):
    original_client = httpx.AsyncClient
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(503, text="retry")
    monkeypatch.setattr(dispatch, "validate_public_https_url", AsyncMock())
    monkeypatch.setattr(dispatch.httpx, "AsyncClient", lambda **kw: original_client(transport=httpx.MockTransport(respond), **kw))
    async with sessions() as db:
        project = uuid.uuid4()
        due = await add_delivery(db, project)
        for kwargs in [{"due": False}, {"active": False}, {"attempts": 3}, {"success": True}]:
            await add_delivery(db, project, **kwargs)
        await add_delivery(db, uuid.uuid4())
        before = datetime.now(timezone.utc)
        assert await dispatch.dispatch_pending_deliveries(db, str(project)) == 0
        assert len(calls) == 1
        assert due.attempts == 1
        assert 55 < (due.next_retry_at - before).total_seconds() < 65
        due.next_retry_at = before - timedelta(seconds=1)
        due.attempts = 2
        await db.flush()
        await dispatch.dispatch_pending_deliveries(db, str(project))
        assert due.attempts == 3 and due.next_retry_at is None


async def test_retry_success_clears_due_and_is_not_repeated(sessions, monkeypatch):
    original_client = httpx.AsyncClient
    monkeypatch.setattr(dispatch, "validate_public_https_url", AsyncMock())
    monkeypatch.setattr(dispatch.httpx, "AsyncClient", lambda **kw: original_client(transport=httpx.MockTransport(lambda req: httpx.Response(204)), **kw))
    async with sessions() as db:
        delivery = await add_delivery(db, uuid.uuid4())
        assert await dispatch.dispatch_pending_deliveries(db) == 1
        assert delivery.success and delivery.next_retry_at is None
        assert await dispatch.dispatch_pending_deliveries(db) == 0
        assert delivery.attempts == 1


async def test_retry_network_failure_is_persisted(sessions, monkeypatch):
    monkeypatch.setattr(dispatch, "validate_public_https_url", AsyncMock(side_effect=ValueError("private URL")))
    async with sessions() as db:
        delivery = await add_delivery(db, uuid.uuid4())
        await dispatch.dispatch_pending_deliveries(db)
        assert delivery.attempts == 1 and not delivery.success
        assert "private URL" in delivery.response_body
        assert delivery.next_retry_at is not None


async def test_scheduler_owns_sessions_recovers_failure_and_cancels(monkeypatch):
    class Session:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        commit = AsyncMock()
        rollback = AsyncMock()
    sessions = []
    def factory():
        session = Session()
        sessions.append(session)
        return session
    completed = asyncio.Event()
    count = 0
    async def batch(db):
        nonlocal count
        count += 1
        if count == 1:
            raise RuntimeError("database unavailable")
        completed.set()
        await asyncio.Event().wait()
    monkeypatch.setattr(dispatch, "dispatch_pending_deliveries", batch)
    task = asyncio.create_task(dispatch.run_retry_scheduler(factory, poll_seconds=0))
    await asyncio.wait_for(completed.wait(), 1)
    await dispatch.stop_retry_scheduler(task)
    assert task.cancelled()
    assert len(sessions) == 2
    assert Session.rollback.await_count == 2


async def test_ingest_rejects_ssrf_before_fetch(monkeypatch):
    monkeypatch.setattr(inbound, "validate_public_https_url", AsyncMock(side_effect=ValueError("private URL")))
    client = MagicMock()
    monkeypatch.setattr(inbound.httpx, "AsyncClient", client)
    result = await inbound._handle_ingest_document(MagicMock(), SimpleNamespace(project_id=uuid.uuid4()), {"file_url": "https://127.0.0.1/private"}, {})
    assert "private URL" in result["error"]
    client.assert_not_called()


def test_signature_accepts_raw_invalid_utf8_and_rejects_nonascii_signature():
    assert verify_inbound_signature(b'\xff', signature(b'\xff'), "test-secret")
    assert not verify_inbound_signature(b'{}', "sha256=\u00e9", "test-secret")

async def test_retry_serialization_covers_commit(monkeypatch):
    entered = asyncio.Event()
    finish = asyncio.Event()
    calls = []
    async def batch(db, project):
        calls.append(db)
        return 0
    first = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    second = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    async def commit():
        entered.set()
        await finish.wait()
    first.commit.side_effect = commit
    monkeypatch.setattr(dispatch, "_dispatch_pending_deliveries", batch)
    task1 = asyncio.create_task(dispatch.dispatch_pending_deliveries(first))
    await asyncio.wait_for(entered.wait(), 1)
    task2 = asyncio.create_task(dispatch.dispatch_pending_deliveries(second))
    await asyncio.sleep(0)
    assert calls == [first]
    finish.set()
    await asyncio.gather(task1, task2)
    assert calls == [first, second]


@pytest.mark.parametrize("status,body,content_type", [(302, b'x', 'text/plain'), (200, b'', 'text/plain'), (200, b'x', 'application/octet-stream'), (200, b'x' * 100, 'text/plain')])
async def test_ingest_rejects_redirect_empty_type_and_size(monkeypatch, status, body, content_type):
    from routers.documents import validation
    original_client = httpx.AsyncClient
    monkeypatch.setattr(validation, "MAX_FILE_SIZE", 50)
    monkeypatch.setattr(inbound, "validate_public_https_url", AsyncMock())
    monkeypatch.setattr(inbound.httpx, "AsyncClient", lambda **kw: original_client(transport=httpx.MockTransport(lambda req: httpx.Response(status, content=body, headers={"content-type": content_type, "location": "https://127.0.0.1/secret"})), **kw))
    db = MagicMock()
    result = await inbound._handle_ingest_document(db, SimpleNamespace(project_id=uuid.uuid4()), {"file_url": "https://example.com/file"}, {})
    assert "error" in result
    db.add.assert_not_called()


async def test_ingest_persists_before_launch_and_compensates(monkeypatch):
    from services.documents import storage
    from routers.documents import ingestion_tasks
    original_client = httpx.AsyncClient
    monkeypatch.setattr(inbound, "validate_public_https_url", AsyncMock())
    monkeypatch.setattr(inbound.httpx, "AsyncClient", lambda **kw: original_client(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=b'hello', headers={"content-type": "text/plain"})), **kw))
    saved = MagicMock()
    deleted = MagicMock()
    started = MagicMock()
    monkeypatch.setattr(storage, "save_original", saved)
    monkeypatch.setattr(storage, "delete_original", deleted)
    monkeypatch.setattr(ingestion_tasks, "_start_ingestion", started)
    db = SimpleNamespace(add=MagicMock(), flush=AsyncMock(), commit=AsyncMock(), rollback=AsyncMock())
    project = uuid.uuid4()
    result = await inbound._handle_ingest_document(db, SimpleNamespace(project_id=project), {"file_url": "https://example.com/file", "filename": "../file.txt", "project_id": str(uuid.uuid4()), "uploaded_by": str(uuid.uuid4())}, {})
    assert result["status"] == "pending"
    doc = db.add.call_args.args[0]
    assert doc.project_id == project and doc.uploaded_by is None
    assert '/' not in doc.filename
    db.commit.assert_awaited_once()
    started.assert_called_once()
    saved.assert_called_once()
    deleted.assert_not_called()
    started.reset_mock()
    db.commit.side_effect = RuntimeError("commit failed")
    with pytest.raises(RuntimeError, match="commit failed"):
        await inbound._handle_ingest_document(db, SimpleNamespace(project_id=project), {"file_url": "https://example.com/file"}, {})
    deleted.assert_called_once()
    db.rollback.assert_awaited_once()
    started.assert_not_called()

@pytest.mark.parametrize("slug", ["test", "unknown"])
async def test_chunked_oversized_public_request_is_rejected_before_handler(client, slug):
    session, handler = client
    consumed = []
    async def body():
        for index in range(4):
            consumed.append(index)
            yield b'x' * 32768
    response = await session.post(f"/webhooks/inbound/{slug}", content=body())
    assert response.status_code == 413
    assert consumed == [0, 1, 2]
    handler.assert_not_awaited()

@pytest.mark.parametrize("stage", ["save", "commit"])
@pytest.mark.parametrize("commit_failure", [False, True])
async def test_ingest_cancellation_finishes_write_and_launch_or_compensation(monkeypatch, stage, commit_failure):
    import threading
    from services.documents import storage
    from routers.documents import ingestion_tasks
    original_client = httpx.AsyncClient
    monkeypatch.setattr(inbound, "validate_public_https_url", AsyncMock())
    monkeypatch.setattr(inbound.httpx, "AsyncClient", lambda **kw: original_client(transport=httpx.MockTransport(lambda req: httpx.Response(200, content=b'hello', headers={"content-type": "text/plain"})), **kw))
    entered = asyncio.Event()
    release_save = threading.Event()
    release_commit = asyncio.Event()
    loop = asyncio.get_running_loop()
    sequence = []
    def save(*args):
        if stage == "save":
            loop.call_soon_threadsafe(entered.set)
            assert release_save.wait(3)
        sequence.append("saved")
    async def commit():
        if stage == "commit":
            entered.set()
            await release_commit.wait()
        if commit_failure:
            raise RuntimeError("commit failed")
        sequence.append("committed")
    def delete(*args):
        assert "saved" in sequence
        sequence.append("deleted")
    monkeypatch.setattr(storage, "save_original", save)
    monkeypatch.setattr(storage, "delete_original", delete)
    monkeypatch.setattr(ingestion_tasks, "_start_ingestion", lambda *args: sequence.append("launched"))
    db = SimpleNamespace(add=MagicMock(), flush=AsyncMock(), commit=commit, rollback=AsyncMock())
    task = asyncio.create_task(inbound._handle_ingest_document(db, SimpleNamespace(project_id=uuid.uuid4()), {"file_url": "https://example.com/file"}, {}))
    await asyncio.wait_for(entered.wait(), 2)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    task.cancel()  # repeated cancellation must not orphan the mutation
    await asyncio.sleep(0)
    release_save.set()
    release_commit.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 3)
    if commit_failure:
        assert sequence == ["saved", "deleted"]
        db.rollback.assert_awaited_once()
    else:
        assert sequence == ["saved", "committed", "launched"]
        db.rollback.assert_not_awaited()
