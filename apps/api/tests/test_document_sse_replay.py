"""Document progress cannot lose a completion before or during subscription."""
import asyncio
import importlib
import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def stream_route(monkeypatch):
    routes = importlib.import_module("routers.documents.router")
    project_id, document_id = str(uuid.uuid4()), str(uuid.uuid4())
    request_db, snapshot_db = MagicMock(), MagicMock()
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=snapshot_db)
    session.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr(routes, "async_session_factory", MagicMock(return_value=session))
    monkeypatch.setattr(routes.doc_service, "get_document", AsyncMock(return_value={"id": document_id, "status": "processing"}))
    routes._doc_subscribers.pop(document_id, None)
    return routes, project_id, document_id, request_db, snapshot_db


def decode(chunk):
    if isinstance(chunk, bytes):
        chunk = chunk.decode()
    return json.loads(chunk.removeprefix("data: ").strip())


@pytest.mark.asyncio
@pytest.mark.parametrize("status,stage,wire_status", [("processed", "complete", "completed"), ("failed", "failed", "failed")])
async def test_late_subscriber_gets_persisted_terminal_state(stream_route, monkeypatch, status, stage, wire_status):
    routes, project, document, request_db, snapshot_db = stream_route
    async def current(db, document_id, project_id):
        assert db is snapshot_db and db is not request_db
        assert (document_id, project_id) == (document, project)
        assert len(routes._doc_subscribers[document]) == 1
        return {"status": status, "error_message": "Failure reason" if status == "failed" else None}
    monkeypatch.setattr(routes.doc_service, "get_document_status", AsyncMock(side_effect=current))
    response = await routes.stream_document_processing(document, project, MagicMock(), request_db)
    events = [decode(chunk) async for chunk in response.body_iterator]
    assert len(events) == 1
    assert events[0]["stage"] == stage
    assert events[0]["status"] == wire_status
    if status == "failed":
        assert events[0]["error_message"] == "Failure reason"
    routes.doc_service.get_document.assert_awaited_once_with(request_db, document, project)
    assert document not in routes._doc_subscribers


@pytest.mark.asyncio
async def test_completion_between_subscription_and_snapshot_is_not_lost(stream_route, monkeypatch):
    routes, project, document, request_db, _ = stream_route
    from routers.documents.ingestion_tasks import _notify_doc_subscribers
    async def current(*_args):
        _notify_doc_subscribers(document, {"stage": "complete", "status": "completed"})
        return {"status": "processing"}
    monkeypatch.setattr(routes.doc_service, "get_document_status", AsyncMock(side_effect=current))
    response = await routes.stream_document_processing(document, project, MagicMock(), request_db)
    events = [decode(chunk) async for chunk in response.body_iterator]
    assert [event["stage"] for event in events] == ["processing", "complete"]
    assert document not in routes._doc_subscribers


@pytest.mark.asyncio
async def test_disconnect_cleans_up_subscriber(stream_route, monkeypatch):
    routes, project, document, request_db, _ = stream_route
    monkeypatch.setattr(routes.doc_service, "get_document_status", AsyncMock(return_value={"status": "processing"}))
    response = await routes.stream_document_processing(document, project, MagicMock(), request_db)
    assert decode(await response.body_iterator.__anext__())["stage"] == "processing"
    assert document in routes._doc_subscribers
    await response.body_iterator.aclose()
    assert document not in routes._doc_subscribers


@pytest.mark.asyncio
async def test_unauthorized_document_does_not_subscribe(stream_route, monkeypatch):
    routes, project, document, request_db, _ = stream_route
    monkeypatch.setattr(routes.doc_service, "get_document", AsyncMock(return_value=None))
    snapshot = AsyncMock()
    monkeypatch.setattr(routes.doc_service, "get_document_status", snapshot)
    with pytest.raises(Exception) as exc:
        await routes.stream_document_processing(document, project, MagicMock(), request_db)
    assert exc.value.status_code == 404
    snapshot.assert_not_awaited()
    assert document not in routes._doc_subscribers
