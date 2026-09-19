"""store_memory tests — creation, TTL, validation."""

import json
import uuid
from datetime import datetime, timedelta

import pytest

from tests.memory.conftest import AGENT_ID, PROJECT_ID, _make_mock_db


@pytest.mark.asyncio
async def test_store_memory_creates_row():
    """store_memory inserts an AgentMemory with correct fields."""
    from services.memory import store_memory

    mock_db = _make_mock_db()

    result = await store_memory(
        db=mock_db,
        agent_id=AGENT_ID,
        project_id=PROJECT_ID,
        memory_type="episodic",
        content={"task": "summarize", "result": "done"},
    )

    assert result["memory_type"] == "episodic"
    assert result["content"]["task"] == "summarize"
    assert result["expires_at"] is None
    assert "id" in result
    assert len(mock_db._added) == 1


@pytest.mark.asyncio
async def test_store_working_memory_has_expiry():
    """store_memory sets expires_at for working memory (default 24h)."""
    from services.memory import store_memory

    mock_db = _make_mock_db()

    result = await store_memory(
        db=mock_db,
        agent_id=AGENT_ID,
        project_id=PROJECT_ID,
        memory_type="working",
        content={"current_task": "embedding"},
    )

    assert result["expires_at"] is not None
    created = datetime.fromisoformat(result["created_at"])
    expires = datetime.fromisoformat(result["expires_at"])
    delta = expires - created
    assert delta == timedelta(hours=24)


@pytest.mark.asyncio
async def test_store_working_memory_custom_ttl():
    """store_memory respects custom ttl_hours for working memory."""
    from services.memory import store_memory

    mock_db = _make_mock_db()

    result = await store_memory(
        db=mock_db,
        agent_id=AGENT_ID,
        project_id=PROJECT_ID,
        memory_type="working",
        content={"context": "test"},
        ttl_hours=2,
    )

    created = datetime.fromisoformat(result["created_at"])
    expires = datetime.fromisoformat(result["expires_at"])
    delta = expires - created
    assert delta == timedelta(hours=2)


@pytest.mark.asyncio
async def test_store_episodic_with_ttl():
    """store_memory applies ttl_hours to episodic memory when provided."""
    from services.memory import store_memory

    mock_db = _make_mock_db()

    result = await store_memory(
        db=mock_db,
        agent_id=AGENT_ID,
        project_id=PROJECT_ID,
        memory_type="episodic",
        content={"result": "reviewed"},
        ttl_hours=48,
    )

    assert result["expires_at"] is not None
    created = datetime.fromisoformat(result["created_at"])
    expires = datetime.fromisoformat(result["expires_at"])
    delta = expires - created
    assert delta == timedelta(hours=48)


@pytest.mark.asyncio
async def test_store_memory_invalid_type_raises():
    """store_memory raises ValueError for invalid memory_type."""
    from services.memory import store_memory

    mock_db = _make_mock_db()

    with pytest.raises(ValueError, match="Invalid memory_type"):
        await store_memory(
            db=mock_db,
            agent_id=AGENT_ID,
            project_id=PROJECT_ID,
            memory_type="invalid",
            content={"bad": True},
        )


@pytest.mark.asyncio
async def test_store_memory_with_embedding():
    """store_memory stores embedding as JSON string."""
    from services.memory import store_memory

    mock_db = _make_mock_db()
    embedding = [0.1, 0.2, 0.3, 0.4]

    result = await store_memory(
        db=mock_db,
        agent_id=AGENT_ID,
        project_id=PROJECT_ID,
        memory_type="semantic",
        content={"fact": "Python is dynamically typed"},
        embedding=embedding,
    )

    stored_obj = mock_db._added[0]
    assert stored_obj.embedding == json.dumps(embedding)


@pytest.mark.asyncio
async def test_store_memory_with_metadata():
    """store_memory stores metadata dict."""
    from services.memory import store_memory

    mock_db = _make_mock_db()
    meta = {"source": "chat", "importance": "high"}

    result = await store_memory(
        db=mock_db,
        agent_id=AGENT_ID,
        project_id=PROJECT_ID,
        memory_type="episodic",
        content={"event": "user asked about auth"},
        metadata=meta,
    )

    stored_obj = mock_db._added[0]
    assert stored_obj.metadata_ == meta
