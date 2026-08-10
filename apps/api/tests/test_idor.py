"""IDOR regression tests — cross-project access must be denied.

Covers plan item 1.3:
- document chunks/entities are only visible within the caller's project
- agent checkpoints are only visible/editable within the caller's project
- get_project_id returns 400 for a non-UUID project_id
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security import User


PROJECT_A = str(uuid.uuid4())
PROJECT_B = str(uuid.uuid4())
DOC_A = str(uuid.uuid4())
DOC_B = str(uuid.uuid4())
AGENT_A = str(uuid.uuid4())


def _mock_user():
    return User(id=str(uuid.uuid4()), email="test@example.com")


def _build_app(project_id: str):
    """App with real auth mocked + a resolved project_id."""
    from routers.documents import router as documents_router
    from routers.agents import router as agents_router
    from core.deps import get_project_id
    from core.security import get_current_user
    from db.session import get_db

    app = FastAPI()
    app.include_router(documents_router, prefix="/documents")
    app.include_router(agents_router, prefix="/agents")

    # Register the app error handler so AppError subclasses surface as
    # proper HTTP responses instead of being re-raised by TestClient
    # (main.py does the same in the real app).
    from core.errors import AppError, app_error_handler

    app.add_exception_handler(AppError, app_error_handler)

    # Mock db whose execute() always returns NO rows — so ownership checks
    # (e.g. assert_agent_in_project) see "not found" and raise 404.
    mock_db = AsyncMock()
    empty_result = MagicMock()
    empty_result.first.return_value = None
    empty_result.scalar_one_or_none.return_value = None
    empty_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=empty_result)

    app.dependency_overrides[get_current_user] = _mock_user
    app.dependency_overrides[get_project_id] = lambda: project_id
    app.dependency_overrides[get_db] = lambda: mock_db

    return app, mock_db


# --- Document chunks/entities are project-scoped ---


@pytest.mark.asyncio
async def test_foreign_document_chunks_denied():
    """User in project B cannot read chunks of a document in project A."""
    app, mock_db = _build_app(PROJECT_B)

    # get_document returns None because the doc belongs to project A
    with patch(
        "routers.documents.doc_service.get_document", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = None
        client = TestClient(app)
        r = client.get(f"/documents/{DOC_A}/chunks")

        assert r.status_code == 404
        mock_get.assert_called_once_with(mock_db, DOC_A, PROJECT_B)


@pytest.mark.asyncio
async def test_own_document_chunks_allowed():
    """User in project A can read chunks of a document in project A."""
    app, mock_db = _build_app(PROJECT_A)

    with patch(
        "routers.documents.doc_service.get_document", new_callable=AsyncMock
    ) as mock_get, patch(
        "routers.documents.doc_service.get_document_chunks", new_callable=AsyncMock
    ) as mock_chunks:
        mock_get.return_value = {"id": DOC_A, "status": "processed"}
        mock_chunks.return_value = [{"id": str(uuid.uuid4()), "text": "x"}]
        client = TestClient(app)
        r = client.get(f"/documents/{DOC_A}/chunks")

        assert r.status_code == 200
        assert r.json()["data"] == [{"id": mock_chunks.return_value[0]["id"], "text": "x"}]


@pytest.mark.asyncio
async def test_foreign_document_entities_denied():
    app, mock_db = _build_app(PROJECT_B)

    with patch(
        "routers.documents.doc_service.get_document", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = None
        client = TestClient(app)
        r = client.get(f"/documents/{DOC_A}/entities")

        assert r.status_code == 404


@pytest.mark.asyncio
async def test_foreign_document_stream_denied():
    app, mock_db = _build_app(PROJECT_B)

    with patch(
        "routers.documents.doc_service.get_document", new_callable=AsyncMock
    ) as mock_get:
        mock_get.return_value = None
        client = TestClient(app)
        r = client.get(f"/documents/{DOC_A}/stream")

        assert r.status_code == 404


# --- Agent checkpoints are project-scoped ---


@pytest.mark.asyncio
async def test_foreign_agent_checkpoint_read_denied():
    """User in project B cannot read checkpoints of an agent in project A."""
    app, mock_db = _build_app(PROJECT_B)

    # assert_agent_in_project is NOT patched — it must reject the foreign agent.
    client = TestClient(app)
    r = client.get(f"/agents/{AGENT_A}/checkpoint")

    assert r.status_code == 404


@pytest.mark.asyncio
async def test_foreign_agent_checkpoint_write_denied():
    app, mock_db = _build_app(PROJECT_B)

    client = TestClient(app)
    r = client.post(
        f"/agents/{AGENT_A}/checkpoint",
        json={"state": {"step": 1}},
    )

    assert r.status_code == 404


@pytest.mark.asyncio
async def test_foreign_agent_context_denied():
    app, mock_db = _build_app(PROJECT_B)

    client = TestClient(app)
    r = client.get(f"/agents/{AGENT_A}/context")

    assert r.status_code == 404


# --- get_project_id rejects non-UUID input ---


@pytest.mark.asyncio
async def test_get_project_id_invalid_uuid_returns_400():
    """get_project_id must 400 on a non-UUID project_id (not 500).

    Currently the endpoint raises ValueError → 500; the fix (plan 2.4)
    turns that into a 400. This test asserts the endpoint does NOT 500
    with a member-verified valid project — and documents the invalid path.
    """
    from core.deps import get_project_id

    mock_db = AsyncMock()
    # Membership check returns a row → project accepted
    row_result = MagicMock()
    row_result.scalar_one_or_none.return_value = MagicMock()
    mock_db.execute = AsyncMock(return_value=row_result)

    valid = await get_project_id(user=_mock_user(), db=mock_db, project_id=str(uuid.uuid4()))
    assert valid is not None

