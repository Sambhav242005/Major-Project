"""Tests for entity extraction pipeline."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import pipelines.entity_extraction as entity_module


# --- Test: spaCy NER extraction ---

def test_spacy_ner_extracts_entities():
    from pipelines.entity_extraction import _spacy_ner

    text = "John Smith works at Google in Mountain View. He met Sarah Jones on January 15, 2024."
    entities = _spacy_ner(text)

    assert len(entities) > 0
    names = [e["name"] for e in entities]
    assert any("John" in n or "Smith" in n or "Google" in n or "Mountain" in n for n in names)


def test_spacy_ner_skips_short_names():
    from pipelines.entity_extraction import _spacy_ner

    text = "A B C D. The quick brown fox jumps over the lazy dog."
    entities = _spacy_ner(text)

    for ent in entities:
        assert len(ent["name"]) >= 2


def test_spacy_ner_maps_types_correctly():
    from pipelines.entity_extraction import _spacy_ner

    text = "Apple Inc. is based in California. Tim Cook is the CEO."
    entities = _spacy_ner(text)

    types = [e["type"] for e in entities]
    valid_types = {"person", "organization", "concept", "location", "date", "other"}
    for t in types:
        assert t in valid_types


# --- Test: Entity merging ---

def test_merge_entities_deduplicates():
    from pipelines.entity_extraction import _merge_entities

    spacy_entities = [
        {"name": "Google", "type": "organization"},
        {"name": "Google Inc.", "type": "organization"},
    ]
    llm_entities = [
        {"name": "Google", "type": "organization", "description": "Tech company"},
    ]

    merged = _merge_entities(spacy_entities, llm_entities)
    assert len(merged) >= 1


def test_merge_entities_uses_llm_description():
    from pipelines.entity_extraction import _merge_entities

    spacy_entities = [{"name": "Microsoft", "type": "organization"}]
    llm_entities = [{"name": "Microsoft", "type": "organization", "description": "Software company"}]

    merged = _merge_entities(spacy_entities, llm_entities)

    assert len(merged) == 1
    assert merged[0]["description"] == "Software company"


def test_merge_entities_prefers_llm_type():
    from pipelines.entity_extraction import _merge_entities

    spacy_entities = [{"name": "Python", "type": "other"}]
    llm_entities = [{"name": "Python", "type": "concept", "description": "Programming language"}]

    merged = _merge_entities(spacy_entities, llm_entities)

    assert merged[0]["type"] == "concept"


# --- Test: Chunk batching ---

def test_extract_cohesive_chunks_batches():
    from pipelines.entity_extraction import _extract_cohesive_chunks

    chunks = [
        {"id": "1", "text": "Short text.", "page_number": 1},
        {"id": "2", "text": "Another short text.", "page_number": 1},
        {"id": "3", "text": "Third piece of text.", "page_number": 2},
    ]

    batches = _extract_cohesive_chunks(chunks, max_tokens=100)

    assert len(batches) >= 1
    for batch in batches:
        assert "text" in batch
        assert "chunk_ids" in batch


# --- Test: LLM extraction (mocked) ---

@pytest.mark.asyncio
async def test_llm_extract_returns_parsed_json():
    with patch.object(entity_module, "chat_completion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = '{"entities": [{"name": "Alice", "type": "person"}], "relationships": []}'

        from pipelines.entity_extraction import _llm_extract

        result = await _llm_extract("Alice works at Acme Corp.")

        assert "entities" in result
        assert "relationships" in result
        assert len(result["entities"]) == 1
        assert result["entities"][0]["name"] == "Alice"


@pytest.mark.asyncio
async def test_llm_extract_handles_invalid_json():
    with patch.object(entity_module, "chat_completion", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "This is not JSON"

        from pipelines.entity_extraction import _llm_extract

        result = await _llm_extract("Some text")

        assert result == {"entities": [], "relationships": []}
