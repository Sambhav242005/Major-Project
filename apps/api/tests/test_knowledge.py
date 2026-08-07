"""Tests for knowledge base service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# --- Test: Search returns formatted results ---

@pytest.mark.asyncio
@patch("services.knowledge.query_chunks")
@patch("services.knowledge.select")
async def test_search_returns_enriched_results(mock_select, mock_query_chunks):
    # Mock ChromaDB results
    mock_query_chunks.return_value = [
        {
            "chunk_id": "chunk-1",
            "document_id": "doc-1",
            "text": "Test chunk text",
            "score": 0.85,
            "page_number": 1,
        }
    ]

    # Mock DB results
    mock_chunk = MagicMock()
    mock_chunk.id = "chunk-1"
    mock_chunk.document_id = "doc-1"
    mock_chunk.page_number = 1
    mock_chunk.chunk_index = 0

    mock_doc = MagicMock()
    mock_doc.filename = "test.pdf"

    mock_db = AsyncMock()

    # Chain the mock calls
    mock_result1 = MagicMock()
    mock_result1.scalar_one_or_none.return_value = mock_chunk

    mock_result2 = MagicMock()
    mock_result2.scalar_one_or_none.return_value = mock_doc

    mock_db.execute = AsyncMock(side_effect=[mock_result1, mock_result2])

    from services.knowledge import search

    results = await search(mock_db, "test query", "proj-1")

    assert len(results) == 1
    assert results[0]["chunk_id"] == "chunk-1"
    assert results[0]["filename"] == "test.pdf"


# --- Test: Search returns empty on no results ---

@pytest.mark.asyncio
@patch("services.knowledge.query_chunks")
async def test_search_returns_empty_when_no_chunks(mock_query_chunks):
    mock_query_chunks.return_value = []

    mock_db = AsyncMock()

    from services.knowledge import search

    results = await search(mock_db, "query", "proj-1")

    assert results == []


# --- Test: Get entity returns None for nonexistent ---

@pytest.mark.asyncio
async def test_get_entity_returns_none_for_nonexistent():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    from services.knowledge import get_entity

    result = await get_entity(mock_db, "nonexistent-id", "proj-1")

    assert result is None


# --- Test: Get graph returns empty when no entities ---

@pytest.mark.asyncio
async def test_get_graph_returns_empty_when_no_entities():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    from services.knowledge import get_graph

    result = await get_graph(mock_db, None, "proj-1")

    assert result == {"nodes": [], "edges": []}
