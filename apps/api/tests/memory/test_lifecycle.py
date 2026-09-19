"""Lifecycle tests — delete, cleanup, checkpoints."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.memory.conftest import AGENT_ID, PROJECT_ID, _make_mock_db


@pytest.mark.asyncio
async def test_delete_memory_removes_row():
    """delete_memory returns True when memory exists."""
    from services.memory import delete_memory
    from db.models import AgentMemory

    mock_db = AsyncMock()
    mem = AgentMemory(
        id=uuid.uuid4(),
        agent_id=uuid.UUID(AGENT_ID),
        project_id=uuid.UUID(PROJECT_ID),
        memory_type="episodic",
        content={"delete": "me"},
        created_at=datetime.utcnow(),
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mem
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.delete = AsyncMock()

    result = await delete_memory(mock_db, str(mem.id), AGENT_ID, PROJECT_ID)

    assert result is True
    mock_db.delete.assert_called_once_with(mem)


@pytest.mark.asyncio
async def test_delete_memory_returns_false_for_nonexistent():
    """delete_memory returns False when memory not found."""
    from services.memory import delete_memory

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await delete_memory(mock_db, str(uuid.uuid4()), AGENT_ID, PROJECT_ID)

    assert result is False


@pytest.mark.asyncio
async def test_cleanup_expired_removes_old_memories():
    """cleanup_expired_memories deletes expired working memories."""
    from services.memory import cleanup_expired_memories

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 3
    mock_db.execute = AsyncMock(return_value=mock_result)

    count = await cleanup_expired_memories(mock_db, AGENT_ID, PROJECT_ID)

    assert count == 3
    mock_db.flush.assert_called_once()


@pytest.mark.asyncio
async def test_save_checkpoint_creates_row():
    """save_checkpoint inserts an AgentCheckpoint."""
    from services.memory import save_checkpoint

    mock_db = _make_mock_db()

    result = await save_checkpoint(
        db=mock_db,
        agent_id=AGENT_ID,
        task_id=str(uuid.uuid4()),
        state={"step": 3, "data": "partial"},
    )

    assert result["state"]["step"] == 3
    assert result["agent_id"] == AGENT_ID
    assert "id" in result
    assert "created_at" in result
    assert len(mock_db._added) == 1


@pytest.mark.asyncio
async def test_save_checkpoint_without_task_id():
    """save_checkpoint works with task_id=None."""
    from services.memory import save_checkpoint

    mock_db = _make_mock_db()

    result = await save_checkpoint(
        db=mock_db,
        agent_id=AGENT_ID,
        task_id=None,
        state={"paused": True},
    )

    assert result["state"]["paused"] is True
    stored = mock_db._added[0]
    assert stored.task_id is None


@pytest.mark.asyncio
async def test_load_latest_checkpoint_returns_most_recent():
    """load_latest_checkpoint returns the newest checkpoint."""
    from services.memory import load_latest_checkpoint
    from db.models import AgentCheckpoint

    mock_db = AsyncMock()
    checkpoint = AgentCheckpoint(
        id=uuid.uuid4(),
        agent_id=uuid.UUID(AGENT_ID),
        task_id=None,
        state={"resumed": True},
        created_at=datetime.utcnow(),
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = checkpoint
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await load_latest_checkpoint(mock_db, AGENT_ID)

    assert result is not None
    assert result["state"]["resumed"] is True


@pytest.mark.asyncio
async def test_load_latest_checkpoint_returns_none_when_empty():
    """load_latest_checkpoint returns None when no checkpoints exist."""
    from services.memory import load_latest_checkpoint

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await load_latest_checkpoint(mock_db, AGENT_ID)

    assert result is None
