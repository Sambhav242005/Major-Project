"""Tests for agents service and pipeline."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_list_agents_returns_empty():
    """list_agents returns empty list when no agents exist."""
    from services.agents import list_agents

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    async def mock_execute(stmt):
        return mock_result

    mock_db.execute = mock_execute

    result = await list_agents(mock_db, str(uuid.uuid4()))
    assert result == []


@pytest.mark.asyncio
async def test_list_agent_types_returns_all():
    """list_agent_types returns all available types."""
    from services.agents import list_agent_types

    types = list_agent_types()
    assert len(types) == 4
    type_names = [t["type"] for t in types]
    assert "summarizer" in type_names
    assert "extractor" in type_names
    assert "qa" in type_names
    assert "reviewer" in type_names


@pytest.mark.asyncio
async def test_create_agent_inserts_row():
    """create_agent should insert a new agent row."""
    from services.agents import create_agent

    mock_db = AsyncMock()
    mock_user = MagicMock()
    mock_user.id = str(uuid.uuid4())

    added_agent = None

    def mock_add(obj):
        nonlocal added_agent
        added_agent = obj

    mock_db.add = mock_add
    mock_db.flush = AsyncMock()

    result = await create_agent(
        db=mock_db,
        user=mock_user,
        project_id=str(uuid.uuid4()),
        name="Test Agent",
        agent_type="summarizer",
    )

    assert result["name"] == "Test Agent"
    assert result["type"] == "summarizer"
    assert result["status"] == "active"
    assert added_agent is not None


@pytest.mark.asyncio
async def test_get_agent_returns_none_for_nonexistent():
    """get_agent returns None for nonexistent agent."""
    from services.agents import get_agent

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    async def mock_execute(stmt):
        return mock_result

    mock_db.execute = mock_execute

    result = await get_agent(mock_db, str(uuid.uuid4()), str(uuid.uuid4()))
    assert result is None


@pytest.mark.asyncio
async def test_delete_agent_returns_false_for_nonexistent():
    """delete_agent returns False for nonexistent agent."""
    from services.agents import delete_agent

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    async def mock_execute(stmt):
        return mock_result

    mock_db.execute = mock_execute

    result = await delete_agent(mock_db, str(uuid.uuid4()), str(uuid.uuid4()))
    assert result is False


def test_get_agent_type_info_returns_info():
    """get_agent_type_info returns info for known types."""
    from pipelines.agent_pipeline import get_agent_type_info

    info = get_agent_type_info("summarizer")
    assert info["name"] == "Document Summarizer"
    assert "system_prompt" in info


def test_get_agent_type_info_returns_fallback():
    """get_agent_type_info returns fallback for unknown types."""
    from pipelines.agent_pipeline import get_agent_type_info

    info = get_agent_type_info("custom_type")
    assert "custom_type" in info["name"]
    assert "system_prompt" in info
