"""Shim — re-exports from pipelines.extraction for backward compatibility."""

from pipelines.extraction import (
    BATCH_SIZE,
    ENTITY_TYPES,
    EXTRACT_PROMPT,
    SPACY_TYPE_MAP,
    _cooccurrence_relationships,
    _extract_cohesive_chunks,
    _llm_extract,
    _merge_entities,
    _nlp,
    _parse_llm_response,
    _spacy_ner,
    extract_entities_from_chunks,
)
from pipelines.llm_client import chat_completion

__all__ = [
    "_spacy_ner",
    "_extract_cohesive_chunks",
    "_llm_extract",
    "_parse_llm_response",
    "_merge_entities",
    "_cooccurrence_relationships",
    "extract_entities_from_chunks",
    "SPACY_TYPE_MAP",
    "ENTITY_TYPES",
    "BATCH_SIZE",
    "EXTRACT_PROMPT",
    "_nlp",
    "chat_completion",
]
