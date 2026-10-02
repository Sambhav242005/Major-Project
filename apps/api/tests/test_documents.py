"""TDD tests for document upload — upload creates pending document row."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# --- Test: Upload creates document with pending status ---

@pytest.mark.asyncio
@patch("services.documents.crud.Document")
async def test_upload_creates_pending_document(MockDocument):
    mock_doc_instance = MagicMock()
    MockDocument.return_value = mock_doc_instance

    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.delete = AsyncMock()

    from services.documents import upload_document

    mock_user = MagicMock(id="550e8400-e29b-41d4-a716-446655440000", email="test@example.com")
    result = await upload_document(
        db=mock_db,
        user=mock_user,
        filename="test.pdf",
        file_type="application/pdf",
        storage_path="projects/proj-1/documents/doc-123/test.pdf",
        project_id="550e8400-e29b-41d4-a716-446655440001",
    )

    assert result["status"] == "pending"
    assert result["filename"] == "test.pdf"
    assert "id" in result
    mock_db.add.assert_called_once_with(mock_doc_instance)


# --- Test: List documents returns list ---

@pytest.mark.asyncio
async def test_list_documents_returns_list():
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.delete = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    from services.documents import list_documents

    result = await list_documents(db=mock_db, project_id="550e8400-e29b-41d4-a716-446655440001")

    assert isinstance(result, list)


# --- Test: Get nonexistent document returns None ---

@pytest.mark.asyncio
async def test_get_nonexistent_document_returns_none():
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.delete = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    from services.documents import get_document

    result = await get_document(db=mock_db, document_id="550e8400-e29b-41d4-a716-446655440099", project_id="550e8400-e29b-41d4-a716-446655440001")

    assert result is None


# --- Test: get_document_chunks returns full text (issue #29) ---

def _chunk_db(chunks):
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = chunks

    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_db = MagicMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_db


def _chunk_stub(chunk_id, text, chunk_index=0, page_number=1, token_count=42):
    stub = MagicMock()
    stub.id = chunk_id
    stub.text = text
    stub.chunk_index = chunk_index
    stub.page_number = page_number
    stub.token_count = token_count
    return stub


DOC_ID = "550e8400-e29b-41d4-a716-4466554400aa"
LONG_TEXT = "L" * 900


@pytest.mark.asyncio
async def test_get_document_chunks_returns_untruncated_text():
    """The detail page renders whole chunks — text must not be clipped."""
    from services.documents import get_document_chunks

    mock_db = _chunk_db([_chunk_stub("chunk-1", LONG_TEXT)])

    result = await get_document_chunks(db=mock_db, document_id=DOC_ID)

    assert result[0]["text"] == LONG_TEXT
    assert result[0]["text_truncated"] is False


@pytest.mark.asyncio
async def test_get_document_chunks_short_text_untouched():
    from services.documents import get_document_chunks

    mock_db = _chunk_db([_chunk_stub("chunk-1", "short chunk")])

    result = await get_document_chunks(db=mock_db, document_id=DOC_ID)

    assert result[0]["text"] == "short chunk"
    assert result[0]["text_truncated"] is False


@pytest.mark.asyncio
async def test_get_document_chunks_preview_opt_in():
    """List/preview callers can still ask for a clipped payload."""
    from services.documents import get_document_chunks

    mock_db = _chunk_db([_chunk_stub("chunk-1", LONG_TEXT)])

    result = await get_document_chunks(db=mock_db, document_id=DOC_ID, text_preview_chars=200)

    assert result[0]["text"] == "L" * 200 + "..."
    assert result[0]["text_truncated"] is True


@pytest.mark.asyncio
async def test_get_document_chunks_keeps_chunk_ordering_fields():
    from services.documents import get_document_chunks

    mock_db = _chunk_db([
        _chunk_stub("chunk-0", "a", chunk_index=0, page_number=1),
        _chunk_stub("chunk-1", "b", chunk_index=1, page_number=1),
    ])

    result = await get_document_chunks(db=mock_db, document_id=DOC_ID)

    # Both chunks on page 1 survive — distinct sections must not collapse.
    assert [c["chunk_index"] for c in result] == [0, 1]
    assert [c["id"] for c in result] == ["chunk-0", "chunk-1"]
