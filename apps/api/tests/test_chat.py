"""Tests for chat service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# --- Test: Create session returns dict ---

@pytest.mark.asyncio
async def test_create_session_returns_dict():
    mock_db = AsyncMock()

    from services.chat import create_session

    mock_user = MagicMock(id="550e8400-e29b-41d4-a716-446655440000")
    result = await create_session(
        db=mock_db,
        user=mock_user,
        project_id="550e8400-e29b-41d4-a716-446655440001",
        title="Test Chat",
    )

    assert "id" in result
    assert result["title"] == "Test Chat"
    mock_db.add.assert_called_once()
    mock_db.flush.assert_called_once()


# --- Test: Create session uses default title ---

@pytest.mark.asyncio
async def test_create_session_uses_default_title():
    mock_db = AsyncMock()

    from services.chat import create_session

    mock_user = MagicMock(id="550e8400-e29b-41d4-a716-446655440000")
    result = await create_session(
        db=mock_db,
        user=mock_user,
        project_id="550e8400-e29b-41d4-a716-446655440001",
    )

    assert result["title"] == "New Chat"


# --- Test: Get session returns None for nonexistent ---

@pytest.mark.asyncio
async def test_get_session_returns_none_for_nonexistent():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    from services.chat import get_session

    result = await get_session(mock_db, "nonexistent", "proj-1")

    assert result is None


# --- Test: List sessions returns list ---

@pytest.mark.asyncio
async def test_list_sessions_returns_list():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    from services.chat import list_sessions

    result = await list_sessions(mock_db, "proj-1")

    assert isinstance(result, list)


# --- Test: Format source block ---

def test_format_source_block():
    from services.chat import _format_source_block

    block = _format_source_block(
        index=1,
        text="This is test content from a document.",
        filename="test.pdf",
        page_number=5,
        doc_id="doc-123",
    )

    assert "[Source 1]" in block
    assert "test.pdf" in block
    assert "5" in block
    assert "This is test content" in block


# --- Test: Send message yields events ---

@pytest.mark.asyncio
@patch("services.chat.query_chunks")
async def test_send_message_yields_events(mock_query_chunks):
    mock_query_chunks.return_value = []

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    from services.chat import send_message

    events = []
    async for event in send_message(
        db=mock_db,
        session_id="session-1",
        message="Hello",
        project_id="proj-1",
    ):
        events.append(event)

    # Should have at least user message saved, citations, done
    assert any(e["type"] == "done" for e in events)
    assert any(e["type"] == "citations" for e in events)
