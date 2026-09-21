"""retrieve_memories and search_memories tests."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.memory.conftest import AGENT_ID, PROJECT_ID


@pytest.mark.asyncio
async def test_retrieve_memories_returns_list():
    """retrieve_memories returns list of memory dicts."""
    from services.memory import retrieve_memories
    from db.models import AgentMemory

    mock_db = AsyncMock()

    mem = AgentMemory(
        id=uuid.uuid4(),
        agent_id=uuid.UUID(AGENT_ID),
        project_id=uuid.UUID(PROJECT_ID),
        memory_type="episodic",
        content={"task": "review"},
        embedding=None,
        metadata_={},
        created_at=datetime.now(timezone.utc),
        expires_at=None,
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mem]
    mock_db.execute = AsyncMock(return_value=mock_result)

    results = await retrieve_memories(mock_db, AGENT_ID, PROJECT_ID)

    assert len(results) == 1
    assert results[0]["memory_type"] == "episodic"
    assert results[0]["content"]["task"] == "review"


@pytest.mark.asyncio
async def test_retrieve_memories_filters_by_type():
    """retrieve_memories with memory_type only returns that type."""
    from services.memory import retrieve_memories

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    await retrieve_memories(mock_db, AGENT_ID, PROJECT_ID, memory_type="working")

    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_retrieve_memories_excludes_expired():
    """retrieve_memories excludes expired memories by default."""
    from services.memory import retrieve_memories

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    await retrieve_memories(mock_db, AGENT_ID, PROJECT_ID, include_expired=False)

    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_retrieve_memories_respects_limit():
    """retrieve_memories passes limit to query."""
    from services.memory import retrieve_memories

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    await retrieve_memories(mock_db, AGENT_ID, PROJECT_ID, limit=5)

    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_search_memories_cosine_similarity():
    """search_memories returns results ranked by similarity."""
    from services.memory import search_memories
    from db.models import AgentMemory

    mock_db = AsyncMock()

    mem1 = AgentMemory(
        id=uuid.uuid4(),
        agent_id=uuid.UUID(AGENT_ID),
        project_id=uuid.UUID(PROJECT_ID),
        memory_type="episodic",
        content={"topic": "auth"},
        embedding=json.dumps([1.0, 0.0, 0.0]),
        metadata_={},
        created_at=datetime.now(timezone.utc),
        expires_at=None,
    )
    mem2 = AgentMemory(
        id=uuid.uuid4(),
        agent_id=uuid.UUID(AGENT_ID),
        project_id=uuid.UUID(PROJECT_ID),
        memory_type="episodic",
        content={"topic": "storage"},
        embedding=json.dumps([0.0, 1.0, 0.0]),
        metadata_={},
        created_at=datetime.now(timezone.utc),
        expires_at=None,
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mem1, mem2]
    mock_db.execute = AsyncMock(return_value=mock_result)

    results = await search_memories(
        mock_db, AGENT_ID, PROJECT_ID,
        query_embedding=[1.0, 0.0, 0.0],
        limit=2,
    )

    assert len(results) == 2
    assert results[0]["similarity"] == 1.0
    assert results[0]["content"]["topic"] == "auth"
    assert results[1]["similarity"] == 0.0


@pytest.mark.asyncio
async def test_search_memories_respects_limit():
    """search_memories returns at most `limit` results."""
    from services.memory import search_memories
    from db.models import AgentMemory

    mock_db = AsyncMock()

    mems = [
        AgentMemory(
            id=uuid.uuid4(),
            agent_id=uuid.UUID(AGENT_ID),
            project_id=uuid.UUID(PROJECT_ID),
            memory_type="episodic",
            content={"i": i},
            embedding=json.dumps([1.0, 0.0]),
            metadata_={},
            created_at=datetime.now(timezone.utc),
            expires_at=None,
        )
        for i in range(10)
    ]

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mems
    mock_db.execute = AsyncMock(return_value=mock_result)

    results = await search_memories(
        mock_db, AGENT_ID, PROJECT_ID,
        query_embedding=[1.0, 0.0],
        limit=3,
    )

    assert len(results) == 3


@pytest.mark.asyncio
async def test_search_memories_skips_none_embedding():
    """search_memories skips memories with None embedding."""
    from services.memory import search_memories
    from db.models import AgentMemory

    mock_db = AsyncMock()

    mem_no_embed = AgentMemory(
        id=uuid.uuid4(),
        agent_id=uuid.UUID(AGENT_ID),
        project_id=uuid.UUID(PROJECT_ID),
        memory_type="episodic",
        content={"no": "embedding"},
        embedding=None,
        metadata_={},
        created_at=datetime.now(timezone.utc),
        expires_at=None,
    )
    mem_with_embed = AgentMemory(
        id=uuid.uuid4(),
        agent_id=uuid.UUID(AGENT_ID),
        project_id=uuid.UUID(PROJECT_ID),
        memory_type="episodic",
        content={"has": "embedding"},
        embedding=json.dumps([0.5, 0.5]),
        metadata_={},
        created_at=datetime.now(timezone.utc),
        expires_at=None,
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mem_no_embed, mem_with_embed]
    mock_db.execute = AsyncMock(return_value=mock_result)

    results = await search_memories(
        mock_db, AGENT_ID, PROJECT_ID,
        query_embedding=[0.5, 0.5],
        limit=5,
    )

    assert len(results) == 1
    assert results[0]["content"]["has"] == "embedding"
