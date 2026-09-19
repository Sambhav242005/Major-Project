"""Merge spaCy and LLM entities and derive co-occurrence relationships."""

from pipelines.extraction.ner import ENTITY_TYPES


def _merge_entities(
    spacy_entities: list[dict],
    llm_entities: list[dict],
) -> list[dict]:
    """Merge spaCy and LLM entities, dedup by normalized name."""
    merged: dict[str, dict] = {}

    for ent in spacy_entities:
        key = ent["name"].lower().strip()
        if key not in merged:
            merged[key] = {
                "name": ent["name"],
                "type": ent["type"],
                "description": "",
            }

    for ent in llm_entities:
        key = ent.get("name", "").lower().strip()
        if not key:
            continue
        if key in merged:
            if ent.get("description"):
                merged[key]["description"] = ent["description"]
            if ent.get("type") and ent["type"] in ENTITY_TYPES:
                merged[key]["type"] = ent["type"]
        else:
            merged[key] = {
                "name": ent["name"],
                "type": ent.get("type", "other"),
                "description": ent.get("description", ""),
            }

    return list(merged.values())


def _cooccurrence_relationships(
    chunks: list[dict],
    entity_names: set[str],
) -> list[dict]:
    """Derive relationships from entity co-occurrence within a chunk.

    When the LLM fails to return explicit relationships we still connect the
    graph by adding an edge between every pair of entities that appear together
    in the same chunk.
    """
    rels: dict[tuple[str, str], str] = {}
    for chunk in chunks:
        text = (chunk.get("text") or "").lower()
        present = [name for name in entity_names if name in text]
        for i in range(len(present)):
            for j in range(i + 1, len(present)):
                a, b = present[i], present[j]
                if (a, b) not in rels and (b, a) not in rels:
                    rels[(a, b)] = "co_occurs_with"
    return [
        {"source": a, "target": b, "relation_type": t, "description": "Mentioned together in the same passage"}
        for (a, b), t in rels.items()
    ]
