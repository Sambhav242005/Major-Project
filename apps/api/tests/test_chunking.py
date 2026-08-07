"""TDD tests for text chunking — correct sizes, overlap, page handling."""

import pytest
from pipelines.chunking import chunk_text, chunk_pages, count_tokens


# --- Test: Short text produces single chunk ---

def test_short_text_single_chunk():
    text = "This is a short document with fewer tokens than the limit."
    chunks = chunk_text(text, max_tokens=600, overlap_tokens=80)

    assert len(chunks) == 1
    assert chunks[0]["text"] == text
    assert chunks[0]["token_count"] <= 600


# --- Test: Long text produces multiple chunks ---

def test_long_text_multiple_chunks():
    # Create text that's clearly over 600 tokens
    text = "word " * 1200  # ~1200 tokens
    chunks = chunk_text(text, max_tokens=600, overlap_tokens=80)

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk["token_count"] <= 600


# --- Test: Chunks have overlap ---

def test_chunks_have_overlap():
    text = "alpha " * 800  # ~800 tokens
    chunks = chunk_text(text, max_tokens=600, overlap_tokens=80)

    if len(chunks) >= 2:
        # Second chunk should contain some tokens from end of first chunk
        chunk1_tokens = set(chunks[0]["text"].split())
        chunk2_tokens = set(chunks[1]["text"].split())
        overlap = chunk1_tokens & chunk2_tokens
        assert len(overlap) > 0, "Chunks should have overlapping tokens"


# --- Test: Page number is preserved ---

def test_page_number_preserved():
    text = "word " * 100
    chunks = chunk_text(text, max_tokens=600, page_number=5)

    for chunk in chunks:
        assert chunk["page_number"] == 5


# --- Test: Chunk indices are sequential ---

def test_chunk_indices_sequential():
    text = "word " * 1200
    chunks = chunk_text(text, max_tokens=600, overlap_tokens=80)

    for i, chunk in enumerate(chunks):
        assert chunk["chunk_index"] == i


# --- Test: chunk_pages handles multiple pages ---

def test_chunk_pages_multiple_pages():
    pages = [
        {"text": "Page one content. " * 50, "page_number": 1},
        {"text": "Page two content. " * 50, "page_number": 2},
        {"text": "Page three content. " * 50, "page_number": 3},
    ]
    chunks = chunk_pages(pages, max_tokens=600, overlap_tokens=80)

    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk["token_count"] <= 600


# --- Test: Empty pages are skipped ---

def test_empty_pages_skipped():
    pages = [
        {"text": "", "page_number": 1},
        {"text": "Real content here. " * 20, "page_number": 2},
    ]
    chunks = chunk_pages(pages, max_tokens=600)

    assert len(chunks) > 0
    assert chunks[0]["page_number"] == 2


# --- Test: count_tokens works ---

def test_count_tokens():
    text = "Hello world"
    tokens = count_tokens(text)
    assert tokens > 0
    assert tokens < 10  # "Hello world" should be very few tokens
