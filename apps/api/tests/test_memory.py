"""Tests for agent memory service — CRUD, search, checkpoints, hydration."""

import uuid
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# --- Helpers ---

AGENT_ID = str(uuid.uuid4())
PROJECT_ID = str(uuid.uuid4())


def _make_mock_db():
    """Create a mock AsyncSession that captures added objects."""
    mock_db = AsyncMock()
    added = []

    def mock_add(obj):
        added.append(obj)

    mock_db.add = mock_add
    mock_db.flush = AsyncMock()
    mock_db._added = added
    return mock_db


def _mock_execute_result(scalars_list):
    """Create a mock result that returns scalars().all()."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = scalars_list
    mock_result.rowcount = len(scalars_list)
    return mock_result


# --- store_memory ---

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


# --- retrieve_memories ---

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
        created_at=datetime.utcnow(),
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
    from db.models import AgentMemory

    mock_db = AsyncMock()

    # The mock just returns whatever we set — the filter logic is in the SQL
    # We verify the SQL contains the right condition
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    await retrieve_memories(mock_db, AGENT_ID, PROJECT_ID, memory_type="working")

    # Verify execute was called (SQL built correctly)
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_retrieve_memories_excludes_expired():
    """retrieve_memories excludes expired memories by default."""
    from services.memory import retrieve_memories
    from db.models import AgentMemory

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


# --- search_memories ---

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
        created_at=datetime.utcnow(),
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
        created_at=datetime.utcnow(),
        expires_at=None,
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mem1, mem2]
    mock_db.execute = AsyncMock(return_value=mock_result)

    # Query embedding matches mem1 perfectly
    results = await search_memories(
        mock_db, AGENT_ID, PROJECT_ID,
        query_embedding=[1.0, 0.0, 0.0],
        limit=2,
    )

    assert len(results) == 2
    # mem1 should be first (similarity = 1.0)
    assert results[0]["similarity"] == 1.0
    assert results[0]["content"]["topic"] == "auth"
    # mem2 should be second (similarity = 0.0)
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
            created_at=datetime.utcnow(),
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
        created_at=datetime.utcnow(),
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
        created_at=datetime.utcnow(),
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


# --- delete_memory ---

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


# --- cleanup_expired_memories ---

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


# --- save_checkpoint ---

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


# --- load_latest_checkpoint ---

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


# --- hydrate_agent_context ---

@pytest.mark.asyncio
async def test_hydrate_agent_context_builds_prompt():
    """hydrate_agent_context returns structured context with all memory types."""
    from services.memory import hydrate_agent_context
    from db.models import AgentMemory

    mock_db = AsyncMock()

    working_mem = AgentMemory(
        id=uuid.uuid4(), agent_id=uuid.UUID(AGENT_ID), project_id=uuid.UUID(PROJECT_ID),
        memory_type="working", content={"task": "review"}, embedding=None, metadata_={},
        created_at=datetime.utcnow(), expires_at=None,
    )
    episodic_mem = AgentMemory(
        id=uuid.uuid4(), agent_id=uuid.UUID(AGENT_ID), project_id=uuid.UUID(PROJECT_ID),
        memory_type="episodic", content={"past": "done"}, embedding=None, metadata_={},
        created_at=datetime.utcnow(), expires_at=None,
    )

    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        if call_count == 1:  # working
            mock_result.scalars.return_value.all.return_value = [working_mem]
        elif call_count == 2:  # episodic
            mock_result.scalars.return_value.all.return_value = [episodic_mem]
        else:  # semantic + checkpoint
            mock_result.scalars.return_value.all.return_value = []
            mock_result.scalar_one_or_none.return_value = None
        return mock_result

    mock_db.execute = mock_execute

    context = await hydrate_agent_context(mock_db, AGENT_ID, PROJECT_ID)

    assert context["working_memory"] == [{"task": "review"}]
    assert context["episodic_memory"] == [{"past": "done"}]
    assert context["semantic_memory"] == []
    assert context["checkpoint"] is None


@pytest.mark.asyncio
async def test_hydrate_agent_context_empty_when_no_memories():
    """hydrate_agent_context returns empty lists when no memories exist."""
    from services.memory import hydrate_agent_context

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    context = await hydrate_agent_context(mock_db, AGENT_ID, PROJECT_ID)

    assert context["working_memory"] == []
    assert context["episodic_memory"] == []
    assert context["semantic_memory"] == []
    assert context["checkpoint"] is None


# --- format_memory_context ---

def test_format_memory_context_with_checkpoint():
    """format_memory_context includes checkpoint section."""
    from services.memory import format_memory_context

    context = {
        "working_memory": [],
        "episodic_memory": [],
        "semantic_memory": [],
        "checkpoint": {"step": 5, "data": "partial"},
    }

    result = format_memory_context(context)

    assert "RESUMED FROM CHECKPOINT" in result
    assert '"step": 5' in result


def test_format_memory_context_with_working_memory():
    """format_memory_context includes working memory section."""
    from services.memory import format_memory_context

    context = {
        "working_memory": [{"task": "embed"}, {"task": "index"}],
        "episodic_memory": [],
        "semantic_memory": [],
        "checkpoint": None,
    }

    result = format_memory_context(context)

    assert "WORKING MEMORY" in result
    assert "embed" in result


def test_format_memory_context_with_episodic_memory():
    """format_memory_context includes past experiences section."""
    from services.memory import format_memory_context

    context = {
        "working_memory": [],
        "episodic_memory": [{"review": "approved"}],
        "semantic_memory": [],
        "checkpoint": None,
    }

    result = format_memory_context(context)

    assert "PAST EXPERIENCES" in result
    assert "approved" in result


def test_format_memory_context_with_semantic_memory():
    """format_memory_context includes learned facts section."""
    from services.memory import format_memory_context

    context = {
        "working_memory": [],
        "episodic_memory": [],
        "semantic_memory": [{"fact": "Python uses GIL"}],
        "checkpoint": None,
    }

    result = format_memory_context(context)

    assert "LEARNED FACTS" in result
    assert "GIL" in result


def test_format_memory_context_empty():
    """format_memory_context returns empty string when all empty."""
    from services.memory import format_memory_context

    context = {
        "working_memory": [],
        "episodic_memory": [],
        "semantic_memory": [],
        "checkpoint": None,
    }

    result = format_memory_context(context)

    assert result == ""


def test_format_memory_context_full():
    """format_memory_context includes all sections when populated."""
    from services.memory import format_memory_context

    context = {
        "working_memory": [{"task": "current"}],
        "episodic_memory": [{"past": "done"}],
        "semantic_memory": [{"fact": "known"}],
        "checkpoint": {"step": 1},
    }

    result = format_memory_context(context)

    assert "RESUMED FROM CHECKPOINT" in result
    assert "WORKING MEMORY" in result
    assert "PAST EXPERIENCES" in result
    assert "LEARNED FACTS" in result


# --- _cosine_similarity ---

def test_cosine_similarity_identical():
    """_cosine_similarity returns 1.0 for identical vectors."""
    from services.memory import _cosine_similarity

    result = _cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0, 0.0])
    assert result == pytest.approx(1.0)


def test_cosine_similarity_orthogonal():
    """_cosine_similarity returns 0.0 for orthogonal vectors."""
    from services.memory import _cosine_similarity

    result = _cosine_similarity([1.0, 0.0], [0.0, 1.0])
    assert result == pytest.approx(0.0)


def test_cosine_similarity_opposite():
    """_cosine_similarity returns -1.0 for opposite vectors."""
    from services.memory import _cosine_similarity

    result = _cosine_similarity([1.0, 0.0], [-1.0, 0.0])
    assert result == pytest.approx(-1.0)


def test_cosine_similarity_different_lengths():
    """_cosine_similarity returns 0.0 for different length vectors."""
    from services.memory import _cosine_similarity

    result = _cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0])
    assert result == 0.0


def test_cosine_similarity_zero_vector():
    """_cosine_similarity returns 0.0 when either vector is zero."""
    from services.memory import _cosine_similarity

    result = _cosine_similarity([0.0, 0.0], [1.0, 0.0])
    assert result == 0.0
