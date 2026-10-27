"""Tests for chat service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# --- Test: Create session returns dict ---

@pytest.mark.asyncio
async def test_create_session_returns_dict():
    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.delete = AsyncMock()

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
    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.delete = AsyncMock()

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
    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.delete = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    from services.chat import get_session

    result = await get_session(
        mock_db,
        "550e8400-e29b-41d4-a716-446655440002",
        "550e8400-e29b-41d4-a716-446655440001",
    )

    assert result is None


# --- Test: List sessions returns list ---

@pytest.mark.asyncio
async def test_list_sessions_returns_list():
    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.delete = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    from services.chat import list_sessions

    result = await list_sessions(
        mock_db,
        "550e8400-e29b-41d4-a716-446655440001",
    )

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
@pytest.mark.parametrize("use_selection", [False, True])
@patch("services.chat.streaming.query_chunks")
async def test_send_message_yields_events(mock_query_chunks, monkeypatch, use_selection):
    mock_query_chunks.return_value = []
    from pipelines.llm_client import GenerationConfig
    from core.config import settings as app_settings
    # Selections record the user-facing provider (e.g. "groq") even though the
    # wire adapter maps hosted providers to an OpenAI-compatible client.
    selected = GenerationConfig("openai", "selected-model", "https://api.groq.com/openai/v1", "test-key", requested_provider="groq")
    expected = (
        {"provider": "groq", "model": selected.model}
        if use_selection
        else {"provider": "configured", "model": app_settings.LLM_CHAT_MODEL}
    )
    async def successful_stream(**kwargs):
        assert kwargs.get("generation") == (selected if use_selection else None)
        yield "A complete answer"
    monkeypatch.setattr("pipelines.llm_client.chat_completion_stream", successful_stream)
    monkeypatch.setattr("services.webhooks.fire_event", AsyncMock())

    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.delete = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    from services.chat import send_message

    events = []
    async for event in send_message(
        db=mock_db,
        session_id="550e8400-e29b-41d4-a716-446655440002",
        message="Hello",
        project_id="550e8400-e29b-41d4-a716-446655440001",
        actor_id="550e8400-e29b-41d4-a716-446655440000",
        **({"generation": selected} if use_selection else {}),
    ):
        events.append(event)

    # Should have at least user message saved, citations, done
    assert any(e["type"] == "done" for e in events)
    assert any(e["type"] == "citations" for e in events)
    assert not any(e["type"] == "error" for e in events)

    # The resolved generation is announced before streaming and recorded on the
    # saved assistant answer so later model changes cannot mislabel old rows.
    assert any(
        e.get("type") == "generation" and e.get("provider") == expected["provider"]
        and e.get("model") == expected["model"]
        for e in events
    )
    from db.models import ChatMessage
    saved_messages = [call.args[0] for call in mock_db.add.call_args_list if isinstance(call.args[0], ChatMessage)]
    assert [(item.role, item.content) for item in saved_messages] == [("user", "Hello"), ("assistant", "A complete answer")]
    saved_user, saved_assistant = saved_messages
    assert saved_user.generation_provider is None and saved_user.generation_model is None
    assert saved_assistant.generation_provider == expected["provider"]
    assert saved_assistant.generation_model == expected["model"]

    # Credential isolation: the user-supplied API key never reaches an event.
    import json as _json
    serialized = _json.dumps(events)
    assert "test-key" not in serialized
    assert "api_key" not in serialized


@pytest.mark.asyncio
async def test_get_session_exposes_recorded_generation():
    import uuid as _uuid
    from datetime import datetime, timezone

    from services.chat import get_session
    from db.models import ChatMessage, ChatSession

    session = ChatSession(id=_uuid.uuid4(), created_at=datetime.now(timezone.utc))
    messages = [
        ChatMessage(id=_uuid.uuid4(), role="user", content="Hello", created_at=datetime.now(timezone.utc)),
        ChatMessage(
            id=_uuid.uuid4(), role="assistant", content="Answer",
            generation_provider="groq", generation_model="selected-model",
            created_at=datetime.now(timezone.utc),
        ),
    ]
    mock_db = MagicMock()
    results = [MagicMock(), MagicMock()]
    results[0].scalar_one_or_none.return_value = session
    results[1].scalars.return_value.all.return_value = messages
    mock_db.execute = AsyncMock(side_effect=results)

    result = await get_session(
        mock_db,
        str(session.id),
        "550e8400-e29b-41d4-a716-446655440001",
    )

    assert result is not None
    assert result["messages"][0]["generation"] is None
    assert result["messages"][1]["generation"] == {"provider": "groq", "model": "selected-model"}
