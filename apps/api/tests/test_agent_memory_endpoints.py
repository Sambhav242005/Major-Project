"""Tests for agent memory API endpoints — verifies router delegates to service correctly."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security import User


# --- Fixtures ---

APP_ID = str(uuid.uuid4())
PROJECT_ID = str(uuid.uuid4())


def _mock_user():
    return User(id=str(uuid.uuid4()), email="test@example.com", role="authenticated")


def _app_with_overrides():
    """Create a test FastAPI app with mocked auth and db dependencies."""
    from routers.agents import router
    from core.deps import get_project_id
    from core.security import get_current_user
    from db.session import get_db

    app = FastAPI()
    app.include_router(router, prefix="/agents")

    mock_db = AsyncMock()

    app.dependency_overrides[get_current_user] = _mock_user
    app.dependency_overrides[get_project_id] = lambda: PROJECT_ID
    app.dependency_overrides[get_db] = lambda: mock_db

    return app, mock_db


@pytest.fixture(autouse=True)
def _bypass_agent_project_guard():
    """Bypass assert_agent_in_project — these tests verify the router
    delegates to the memory service, not project ownership (which is
    covered separately by IDOR tests)."""
    with patch("routers.agents.assert_agent_in_project", new_callable=AsyncMock):
        yield


# --- POST /agents/{id}/memory ---

@pytest.mark.asyncio
async def test_store_memory_endpoint():
    """POST /agents/{id}/memory stores memory and returns it."""
    app, mock_db = _app_with_overrides()

    mock_memory = {
        "id": str(uuid.uuid4()),
        "memory_type": "episodic",
        "content": {"task": "review", "result": "approved"},
        "created_at": "2026-01-01T00:00:00",
        "expires_at": None,
    }

    with patch("routers.agents.memory_service.store_memory", new_callable=AsyncMock) as mock_store:
        mock_store.return_value = mock_memory
        client = TestClient(app)
        r = client.post(
            f"/agents/{APP_ID}/memory",
            json={"memory_type": "episodic", "content": {"task": "review", "result": "approved"}},
        )

        assert r.status_code == 200
        data = r.json()
        assert data["memory"]["memory_type"] == "episodic"
        assert data["memory"]["content"]["task"] == "review"
        mock_store.assert_called_once()


@pytest.mark.asyncio
async def test_store_memory_invalid_type_returns_400():
    """POST /agents/{id}/memory returns 400 for invalid memory_type."""
    app, mock_db = _app_with_overrides()

    with patch("routers.agents.memory_service.store_memory", new_callable=AsyncMock) as mock_store:
        mock_store.side_effect = ValueError("Invalid memory_type: bad")
        client = TestClient(app)
        r = client.post(
            f"/agents/{APP_ID}/memory",
            json={"memory_type": "bad", "content": {"x": 1}},
        )

        assert r.status_code == 400
        assert "Invalid memory_type" in r.json()["detail"]


# --- GET /agents/{id}/memory ---

@pytest.mark.asyncio
async def test_list_memory_endpoint():
    """GET /agents/{id}/memory returns list of memories."""
    app, mock_db = _app_with_overrides()

    memories = [
        {"id": str(uuid.uuid4()), "memory_type": "working", "content": {"t": 1}, "metadata": {}, "created_at": "2026-01-01T00:00:00", "expires_at": None},
        {"id": str(uuid.uuid4()), "memory_type": "episodic", "content": {"t": 2}, "metadata": {}, "created_at": "2026-01-01T00:00:01", "expires_at": None},
    ]

    with patch("routers.agents.memory_service.retrieve_memories", new_callable=AsyncMock) as mock_retrieve:
        mock_retrieve.return_value = memories
        client = TestClient(app)
        r = client.get(f"/agents/{APP_ID}/memory")

        assert r.status_code == 200
        data = r.json()
        assert len(data["memories"]) == 2


# --- DELETE /agents/{id}/memory/{mem_id} ---

@pytest.mark.asyncio
async def test_delete_memory_endpoint():
    """DELETE /agents/{id}/memory/{mem_id} returns deleted=True."""
    app, mock_db = _app_with_overrides()
    mem_id = str(uuid.uuid4())

    with patch("routers.agents.memory_service.delete_memory", new_callable=AsyncMock) as mock_delete:
        mock_delete.return_value = True
        client = TestClient(app)
        r = client.delete(f"/agents/{APP_ID}/memory/{mem_id}")

        assert r.status_code == 200
        assert r.json()["deleted"] is True


@pytest.mark.asyncio
async def test_delete_memory_not_found_returns_404():
    """DELETE /agents/{id}/memory/{mem_id} returns 404 when not found."""
    app, mock_db = _app_with_overrides()
    mem_id = str(uuid.uuid4())

    with patch("routers.agents.memory_service.delete_memory", new_callable=AsyncMock) as mock_delete:
        mock_delete.return_value = False
        client = TestClient(app)
        r = client.delete(f"/agents/{APP_ID}/memory/{mem_id}")

        assert r.status_code == 404
        assert "Memory not found" in r.json()["detail"]


# --- GET /agents/{id}/memory/search ---

@pytest.mark.asyncio
async def test_search_memory_endpoint():
    """GET /agents/{id}/memory/search returns search results."""
    app, mock_db = _app_with_overrides()

    results = [
        {"id": str(uuid.uuid4()), "memory_type": "episodic", "content": {"match": True}, "metadata": {}, "similarity": 0.95, "created_at": "2026-01-01T00:00:00"},
    ]

    with patch("routers.agents.memory_service.search_memories", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = results
        client = TestClient(app)
        r = client.get(f"/agents/{APP_ID}/memory/search", params={"q": "test query"})

        assert r.status_code == 200
        data = r.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["similarity"] == 0.95


# --- POST /agents/{id}/checkpoint ---

@pytest.mark.asyncio
async def test_save_checkpoint_endpoint():
    """POST /agents/{id}/checkpoint saves checkpoint and returns it."""
    app, mock_db = _app_with_overrides()

    checkpoint = {
        "id": str(uuid.uuid4()),
        "agent_id": APP_ID,
        "state": {"step": 5, "partial": True},
        "created_at": "2026-01-01T00:00:00",
    }

    with patch("routers.agents.memory_service.save_checkpoint", new_callable=AsyncMock) as mock_save:
        mock_save.return_value = checkpoint
        client = TestClient(app)
        r = client.post(
            f"/agents/{APP_ID}/checkpoint",
            json={"state": {"step": 5, "partial": True}},
        )

        assert r.status_code == 200
        data = r.json()
        assert data["checkpoint"]["state"]["step"] == 5


# --- GET /agents/{id}/checkpoint ---

@pytest.mark.asyncio
async def test_get_checkpoint_endpoint():
    """GET /agents/{id}/checkpoint returns latest checkpoint."""
    app, mock_db = _app_with_overrides()

    checkpoint = {
        "id": str(uuid.uuid4()),
        "agent_id": APP_ID,
        "task_id": None,
        "state": {"resumed": True},
        "created_at": "2026-01-01T00:00:00",
    }

    with patch("routers.agents.memory_service.load_latest_checkpoint", new_callable=AsyncMock) as mock_load:
        mock_load.return_value = checkpoint
        client = TestClient(app)
        r = client.get(f"/agents/{APP_ID}/checkpoint")

        assert r.status_code == 200
        data = r.json()
        assert data["checkpoint"]["state"]["resumed"] is True


@pytest.mark.asyncio
async def test_get_checkpoint_none_returns_null():
    """GET /agents/{id}/checkpoint returns null when no checkpoints."""
    app, mock_db = _app_with_overrides()

    with patch("routers.agents.memory_service.load_latest_checkpoint", new_callable=AsyncMock) as mock_load:
        mock_load.return_value = None
        client = TestClient(app)
        r = client.get(f"/agents/{APP_ID}/checkpoint")

        assert r.status_code == 200
        data = r.json()
        assert data["checkpoint"] is None


# --- GET /agents/{id}/context ---

@pytest.mark.asyncio
async def test_get_context_endpoint():
    """GET /agents/{id}/context returns hydrated context."""
    app, mock_db = _app_with_overrides()

    context = {
        "working_memory": [{"task": "current"}],
        "episodic_memory": [{"past": "done"}],
        "semantic_memory": [],
        "checkpoint": None,
    }

    with patch("routers.agents.memory_service.hydrate_agent_context", new_callable=AsyncMock) as mock_hydrate:
        mock_hydrate.return_value = context
        client = TestClient(app)
        r = client.get(f"/agents/{APP_ID}/context")

        assert r.status_code == 200
        data = r.json()
        assert data["context"]["working_memory"] == [{"task": "current"}]
        assert data["context"]["episodic_memory"] == [{"past": "done"}]
