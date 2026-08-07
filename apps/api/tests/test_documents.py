"""TDD tests for document upload — upload creates pending document row."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# --- Test: Upload creates document with pending status ---

@pytest.mark.asyncio
@patch("services.documents.Document")
async def test_upload_creates_pending_document(MockDocument):
    mock_doc_instance = MagicMock()
    MockDocument.return_value = mock_doc_instance

    mock_db = AsyncMock()

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

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    from services.documents import list_documents

    result = await list_documents(db=mock_db, project_id="550e8400-e29b-41d4-a716-446655440001")

    assert isinstance(result, list)


# --- Test: Get nonexistent document returns None ---

@pytest.mark.asyncio
async def test_get_nonexistent_document_returns_none():
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    from services.documents import get_document

    result = await get_document(db=mock_db, document_id="550e8400-e29b-41d4-a716-446655440099", project_id="550e8400-e29b-41d4-a716-446655440001")

    assert result is None
