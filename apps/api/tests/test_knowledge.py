"""Tests for knowledge base service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# --- Test: Search returns formatted results ---

@pytest.mark.asyncio
@patch("services.knowledge.search.query_chunks")
async def test_search_returns_enriched_results(mock_query_chunks):
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
    mock_chunk.chroma_id = "chunk-1"
    mock_chunk.document_id = "doc-1"
    mock_chunk.page_number = 1
    mock_chunk.chunk_index = 0

    mock_doc = MagicMock()
    mock_doc.id = "doc-1"
    mock_doc.filename = "test.pdf"

    mock_db = AsyncMock()

    # Chain the mock calls
    mock_result1 = MagicMock()
    mock_result1.scalars.return_value.all.return_value = [mock_chunk]

    mock_result2 = MagicMock()
    mock_result2.scalars.return_value.all.return_value = [mock_doc]

    mock_db.execute = AsyncMock(side_effect=[mock_result1, mock_result2])

    from services.knowledge import search

    results = await search(mock_db, "test query", "proj-1")

    assert len(results) == 1
    assert results[0]["chunk_id"] == "chunk-1"
    assert results[0]["filename"] == "test.pdf"


# --- Test: Search returns empty on no results ---

@pytest.mark.asyncio
@patch("services.knowledge.search.query_chunks")
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

    result = await get_entity(
        mock_db,
        "550e8400-e29b-41d4-a716-446655440002",
        "550e8400-e29b-41d4-a716-446655440001",
    )

    assert result is None


# --- Test: Get graph returns empty when no entities ---

@pytest.mark.asyncio
async def test_get_graph_returns_empty_when_no_entities():
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    from services.knowledge import get_graph

    result = await get_graph(
        mock_db,
        None,
        "550e8400-e29b-41d4-a716-446655440001",
    )

    assert result == {"nodes": [], "edges": []}


# --- Test: get_entity_chunks exposes dedup fields (issue #29) ---

ENTITY_ID = "550e8400-e29b-41d4-a716-446655440003"
PROJECT_ID = "550e8400-e29b-41d4-a716-446655440001"
DOC_A = "550e8400-e29b-41d4-a716-446655440004"
DOC_B = "550e8400-e29b-41d4-a716-446655440005"


def _entity_chunk_db(chunk_stubs, filename="report.pdf"):
    """Mock db returning: mentions query, then (chunk, doc) per mention."""
    mentions = []
    for stub in chunk_stubs:
        mention = MagicMock()
        mention.chunk_id = stub.id
        mention.mention_text = "mention"
        mention.confidence = 0.9
        mentions.append(mention)

    mention_scalars = MagicMock()
    mention_scalars.all.return_value = mentions
    mention_result = MagicMock()
    mention_result.scalars.return_value = mention_scalars

    side_effect = [mention_result]
    for stub in chunk_stubs:
        chunk_result = MagicMock()
        chunk_result.scalar_one_or_none.return_value = stub

        doc = MagicMock()
        doc.filename = filename

        doc_result = MagicMock()
        doc_result.scalar_one_or_none.return_value = doc

        side_effect.extend([chunk_result, doc_result])

    mock_db = MagicMock()
    mock_db.execute = AsyncMock(side_effect=side_effect)
    return mock_db


def _kb_chunk_stub(chunk_index, page_number=3, document_id=DOC_A, serial=None):
    stub = MagicMock()
    stub.id = f"550e8400-e29b-41d4-a716-{serial if serial is not None else chunk_index:012d}"
    stub.chunk_index = chunk_index
    stub.page_number = page_number
    stub.text = f"section {chunk_index}"
    stub.document_id = document_id
    return stub


@pytest.mark.asyncio
async def test_get_entity_chunks_includes_dedup_fields():
    """The graph page dedups on document_id|chunk_index — both must ship."""
    from services.knowledge import get_entity_chunks

    mock_db = _entity_chunk_db([_kb_chunk_stub(0), _kb_chunk_stub(1)])

    chunks = await get_entity_chunks(mock_db, ENTITY_ID, PROJECT_ID)

    assert [c["chunk_index"] for c in chunks] == [0, 1]
    assert all(c["document_id"] == DOC_A for c in chunks)


@pytest.mark.asyncio
async def test_get_entity_chunks_distinguishes_same_page_sections():
    """Two distinct chunks in one document stay distinguishable by the key."""
    from services.knowledge import get_entity_chunks

    mock_db = _entity_chunk_db([_kb_chunk_stub(0), _kb_chunk_stub(1)])

    chunks = await get_entity_chunks(mock_db, ENTITY_ID, PROJECT_ID)

    keys = {(c["document_id"], c["chunk_index"]) for c in chunks}
    assert len(keys) == 2


@pytest.mark.asyncio
async def test_get_entity_chunks_distinguishes_same_filename_across_documents():
    """Two uploads named report.pdf must not collide.

    chunk_index is a position within one document's chunk list, so two
    documents produce the same indices. Only document_id separates them.
    """
    from services.knowledge import get_entity_chunks

    mock_db = _entity_chunk_db(
        [
            _kb_chunk_stub(0, document_id=DOC_A, serial=1),
            _kb_chunk_stub(0, document_id=DOC_B, serial=2),
        ]
    )

    chunks = await get_entity_chunks(mock_db, ENTITY_ID, PROJECT_ID)

    # Identical filename and page on purpose — only the key separates them.
    assert chunks[0]["filename"] == chunks[1]["filename"]
    assert chunks[0]["chunk_index"] == chunks[1]["chunk_index"]
    assert len({(c["document_id"], c["chunk_index"]) for c in chunks}) == 2
