"""Hydration tests — hydrate_agent_context and format_memory_context."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.memory.conftest import AGENT_ID, PROJECT_ID


@pytest.mark.asyncio
async def test_hydrate_agent_context_builds_prompt():
    """hydrate_agent_context returns structured context with all memory types."""
    from services.memory import hydrate_agent_context
    from db.models import AgentMemory

    mock_db = AsyncMock()

    working_mem = AgentMemory(
        id=uuid.uuid4(), agent_id=uuid.UUID(AGENT_ID), project_id=uuid.UUID(PROJECT_ID),
        memory_type="working", content={"task": "review"}, embedding=None, metadata_={},
        created_at=datetime.now(timezone.utc), expires_at=None,
    )
    episodic_mem = AgentMemory(
        id=uuid.uuid4(), agent_id=uuid.UUID(AGENT_ID), project_id=uuid.UUID(PROJECT_ID),
        memory_type="episodic", content={"past": "done"}, embedding=None, metadata_={},
        created_at=datetime.now(timezone.utc), expires_at=None,
    )

    call_count = 0

    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        if call_count == 1:
            mock_result.scalars.return_value.all.return_value = [working_mem]
        elif call_count == 2:
            mock_result.scalars.return_value.all.return_value = [episodic_mem]
        else:
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
