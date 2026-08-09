"""Tests for MCP service — MCP 2026-07-28 aligned."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_list_connections_returns_empty():
    """list_connections returns empty list when no connections exist."""
    from services.mcp import list_connections

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    async def mock_execute(stmt):
        return mock_result

    mock_db.execute = mock_execute

    result = await list_connections(mock_db, str(uuid.uuid4()))
    assert result == []


@pytest.mark.asyncio
async def test_get_connection_returns_connection():
    """get_connection returns a connection when found."""
    from services.mcp import get_connection

    mock_conn = MagicMock()
    mock_conn.id = uuid.uuid4()

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_conn

    async def mock_execute(stmt):
        return mock_result

    mock_db.execute = mock_execute

    result = await get_connection(mock_db, str(mock_conn.id), str(uuid.uuid4()))
    assert result == mock_conn


@pytest.mark.asyncio
async def test_get_connection_returns_none_for_nonexistent():
    """get_connection returns None when not found."""
    from services.mcp import get_connection

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    async def mock_execute(stmt):
        return mock_result

    mock_db.execute = mock_execute

    result = await get_connection(mock_db, str(uuid.uuid4()), str(uuid.uuid4()))
    assert result is None


@pytest.mark.asyncio
async def test_create_connection_inserts_row():
    """create_connection inserts a new MCP connection."""
    from services.mcp import create_connection

    mock_db = AsyncMock()
    added_conn = None

    def mock_add(obj):
        nonlocal added_conn
        added_conn = obj

    mock_db.add = mock_add
    mock_db.flush = AsyncMock()

    result = await create_connection(
        db=mock_db,
        project_id=str(uuid.uuid4()),
        direction="sender",
        name="Test Sender",
        endpoint_url="https://example.com/mcp",
    )

    assert result["name"] == "Test Sender"
    assert result["direction"] == "sender"
    assert result["endpoint_url"] == "https://example.com/mcp"
    assert result["status"] == "disconnected"
    assert added_conn is not None


@pytest.mark.asyncio
async def test_delete_connection_returns_false_for_nonexistent():
    """delete_connection returns False for nonexistent connection."""
    from services.mcp import delete_connection

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    async def mock_execute(stmt):
        return mock_result

    mock_db.execute = mock_execute

    result = await delete_connection(mock_db, str(uuid.uuid4()), str(uuid.uuid4()))
    assert result is False


@pytest.mark.asyncio
async def test_search_knowledge_base_calls_search():
    """search_knowledge_base delegates to knowledge service search."""
    from services.mcp import search_knowledge_base

    mock_db = AsyncMock()

    with pytest.MonkeyPatch.context() as m:
        mock_search = AsyncMock(return_value=[{"text": "test", "score": 0.9}])
        m.setattr("services.knowledge.search", mock_search)

        result = await search_knowledge_base(
            db=mock_db,
            project_id=str(uuid.uuid4()),
            query="test query",
            top_k=3,
        )

        assert len(result) == 1
        assert result[0]["text"] == "test"
