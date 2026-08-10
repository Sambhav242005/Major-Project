"""Entity extraction pipeline — spaCy NER + LLM refinement + dedup."""

import json
import logging
import uuid
from collections import defaultdict

import spacy
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Entity, EntityMention, Relationship, DocumentChunk
from pipelines.llm_client import chat_completion

logger = logging.getLogger(__name__)

# Load spaCy model once
_nlp = spacy.load("en_core_web_sm")

# Entity type mapping from spaCy → our schema
SPACY_TYPE_MAP = {
    "PERSON": "person",
    "ORG": "organization",
    "GPE": "location",
    "LOC": "location",
    "DATE": "date",
    "TIME": "date",
    "NORP": "concept",
    "EVENT": "concept",
    "WORK_OF_ART": "concept",
    "PRODUCT": "concept",
}

ENTITY_TYPES = {"person", "organization", "concept", "location", "date", "other"}

# Batch size for LLM calls
BATCH_SIZE = 10


def _spacy_ner(text: str) -> list[dict]:
    """Run spaCy NER on text, return normalized entities."""
    doc = _nlp(text)
    entities = []
    seen = set()
    for ent in doc.ents:
        name = ent.text.strip()
        if len(name) < 2 or len(name) > 100:
            continue
        # Skip pure numbers, dates that are just years, etc.
        if name.isdigit():
            continue
        raw_type = SPACY_TYPE_MAP.get(ent.label_, "other")
        key = (name.lower(), raw_type)
        if key not in seen:
            seen.add(key)
            entities.append({"name": name, "type": raw_type})
    return entities


def _extract_cohesive_chunks(chunks: list[dict], max_tokens: int = 1200) -> list[dict]:
    """Combine small consecutive chunks for better entity co-occurrence."""
    batches = []
    current_text = ""
    current_chunks = []

    for chunk in chunks:
        text = chunk.get("text", "")
        if len(current_text) + len(text) > max_tokens * 4 and current_text:
            batches.append({
                "text": current_text,
                "chunk_ids": [c.get("id") for c in current_chunks if c.get("id")],
                "page_numbers": list(set(c.get("page_number", 0) for c in current_chunks)),
            })
            current_text = text
            current_chunks = [chunk]
        else:
            current_text += "\n\n" + text if current_text else text
            current_chunks.append(chunk)

    if current_text:
        batches.append({
            "text": current_text,
            "chunk_ids": [c.get("id") for c in current_chunks if c.get("id")],
            "page_numbers": list(set(c.get("page_number", 0) for c in current_chunks)),
        })

    return batches


EXTRACT_PROMPT = """You are an entity and relationship extractor. Given a text passage, extract:

1. **Entities**: People, organizations, concepts, locations, dates mentioned in the text.
2. **Relationships**: Connections between extracted entities (e.g., "works_at", "located_in", "mentions").

Return ONLY valid JSON in this format:
{{
  "entities": [
    {{"name": "Entity Name", "type": "person|organization|concept|location|date", "description": "Brief description"}}
  ],
  "relationships": [
    {{"source": "Entity A Name", "target": "Entity B Name", "relation_type": "relationship_name", "description": "Brief description"}}
  ]
}}

Rules:
- Only extract entities that appear in the text
- Keep entity names consistent (use the full name, not abbreviations)
- Relationships must reference two entities from the entities list
- type must be one of: person, organization, concept, location, date
- Be precise — do not hallucinate entities or relationships not in the text

Text:
{text}"""


async def _llm_extract(text: str) -> dict:
    """Call LLM to extract entities and relationships from text.

    Returns {"entities": [...], "relationships": [...]}. On any failure
    returns empty lists — the caller falls back to co-occurrence edges so
    the graph stays connected even if the LLM errors out.
    """

    prompt = EXTRACT_PROMPT.format(text=text[:8000])  # Truncate to avoid token limits
    messages = [
        {"role": "system", "content": "You are an expert entity extractor. Output only valid JSON."},
        {"role": "user", "content": prompt},
    ]

    try:
        # Note: the default LLM_MODEL is a reasoning model (qwen3.6-27b) that
        # burns its whole token budget on <think> blocks and never emits the
        # JSON — Groq then fails with json_validate_failed. Use a fast
        # non-reasoning model for extraction, and rely on prompt instructions
        # plus a defensive parser instead of response_format=json_object.
        response = await chat_completion(
            messages=messages,
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=2000,
        )
        return _parse_llm_response(response)
    except Exception as e:
        logger.warning(f"LLM extraction failed (falling back to co-occurrence): {e}")
        return {"entities": [], "relationships": []}


def _parse_llm_response(response: str) -> dict:
    """Parse LLM JSON response defensively — strip code fences/markdown."""
    text = response.strip()
    # Strip ```json ... ``` fences if present
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text
        text = text.strip()
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # Try to find the first {...} block
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                result = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                logger.warning("LLM returned unparseable JSON")
                return {"entities": [], "relationships": []}
        else:
            logger.warning("LLM returned no JSON object")
            return {"entities": [], "relationships": []}
    return {
        "entities": result.get("entities", []),
        "relationships": result.get("relationships", []),
    }


def _merge_entities(
    spacy_entities: list[dict],
    llm_entities: list[dict],
) -> list[dict]:
    """Merge spaCy and LLM entities, dedup by normalized name."""
    merged = {}

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
            # LLM description takes priority
            if ent.get("description"):
                merged[key]["description"] = ent["description"]
            # LLM type takes priority if more specific
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

    When the LLM fails to return explicit relationships (e.g. the provider
    rejects JSON mode), we still connect the graph by adding an edge between
    every pair of entities that appear together in the same chunk. This
    guarantees the knowledge graph is navigable so agents can hop.
    """
    rels: dict[tuple[str, str], str] = {}  # (source, target) -> relation_type
    for chunk in chunks:
        text = (chunk.get("text") or "").lower()
        present = [name for name in entity_names if name in text]
        # Sort deterministically: earlier-in-alphabet is the source.
        for i in range(len(present)):
            for j in range(i + 1, len(present)):
                a, b = present[i], present[j]
                if (a, b) not in rels and (b, a) not in rels:
                    rels[(a, b)] = "co_occurs_with"
    return [
        {"source": a, "target": b, "relation_type": t, "description": "Mentioned together in the same passage"}
        for (a, b), t in rels.items()
    ]


async def extract_entities_from_chunks(
    db: AsyncSession,
    chunks: list[dict],
    project_id: str,
    document_id: str,
) -> int:
    """Extract entities and relationships from document chunks.

    Args:
        db: Database session
        chunks: List of chunk dicts with 'text', 'chunk_index', 'id'
        project_id: Project UUID string
        document_id: Document UUID string

    Returns:
        Number of entities extracted.
    """
    if not chunks:
        return 0

    # Step 1: Run spaCy NER on all chunks
    all_spacy_entities = []
    for chunk in chunks:
        spacy_ents = _spacy_ner(chunk.get("text", ""))
        all_spacy_entities.extend(spacy_ents)

    # Step 2: Batch chunks for LLM extraction
    batches = _extract_cohesive_chunks(chunks)
    all_llm_entities = []
    all_llm_relationships = []

    for batch in batches:
        result = await _llm_extract(batch["text"])
        all_llm_entities.extend(result["entities"])
        all_llm_relationships.extend(result["relationships"])

    # Step 3: Merge and dedup entities
    merged_entities = _merge_entities(all_spacy_entities, all_llm_entities)

    # Step 3b: If the LLM returned no relationships, derive edges from
    # co-occurrence so the graph stays connected (agents can still hop).
    if not all_llm_relationships:
        cooccurrence_names = {e["name"].lower().strip() for e in merged_entities if e["name"].strip()}
        all_llm_relationships = _cooccurrence_relationships(chunks, cooccurrence_names)
        if all_llm_relationships:
            logger.info(
                f"LLM returned no relationships; derived {len(all_llm_relationships)} "
                f"co-occurrence edges for document {document_id}"
            )

    # Step 4: Store entities in DB
    entity_map = {}  # name_lower -> entity_id

    for ent in merged_entities:
        name = ent["name"]
        ent_type = ent["type"]
        name_lower = name.lower().strip()

        # Check if entity already exists in this project
        stmt = select(Entity).where(
            Entity.project_id == uuid.UUID(project_id),
            Entity.name.ilike(name),
            Entity.type == ent_type,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            entity_map[name_lower] = str(existing.id)
            # Update description if we have a better one and existing is empty
            if ent.get("description") and not existing.description:
                existing.description = ent["description"]
                await db.flush()
        else:
            new_entity = Entity(
                project_id=uuid.UUID(project_id),
                name=name,
                type=ent_type,
                description=ent.get("description", ""),
                first_seen_document_id=uuid.UUID(document_id),
            )
            db.add(new_entity)
            await db.flush()
            entity_map[name_lower] = str(new_entity.id)

    # Step 5: Store entity mentions
    for chunk in chunks:
        chunk_text = chunk.get("text", "")
        chunk_id = chunk.get("id")
        spacy_ents = _spacy_ner(chunk_text)

        for ent in spacy_ents:
            name_lower = ent["name"].lower().strip()
            if name_lower in entity_map:
                mention = EntityMention(
                    entity_id=uuid.UUID(entity_map[name_lower]),
                    document_id=uuid.UUID(document_id),
                    chunk_id=uuid.UUID(chunk_id) if chunk_id else None,
                    mention_text=ent["name"],
                    confidence=0.8,  # spaCy confidence
                )
                db.add(mention)

    await db.flush()

    # Step 6: Store relationships
    for rel in all_llm_relationships:
        source_name = rel.get("source", "").lower().strip()
        target_name = rel.get("target", "").lower().strip()

        if source_name in entity_map and target_name in entity_map:
            # Check for duplicate relationship
            stmt = select(Relationship).where(
                Relationship.project_id == uuid.UUID(project_id),
                Relationship.source_entity_id == uuid.UUID(entity_map[source_name]),
                Relationship.target_entity_id == uuid.UUID(entity_map[target_name]),
                Relationship.relation_type == rel.get("relation_type", ""),
            )
            result = await db.execute(stmt)
            existing_rel = result.scalar_one_or_none()

            if not existing_rel:
                new_rel = Relationship(
                    project_id=uuid.UUID(project_id),
                    source_entity_id=uuid.UUID(entity_map[source_name]),
                    target_entity_id=uuid.UUID(entity_map[target_name]),
                    relation_type=rel.get("relation_type", "related_to"),
                    description=rel.get("description", ""),
                    confidence=0.7,
                    source_document_id=uuid.UUID(document_id),
                )
                db.add(new_rel)

    await db.flush()

    logger.info(
        f"Extracted {len(merged_entities)} entities, "
        f"{len(all_llm_relationships)} relationships for document {document_id}"
    )

    # Fire entity.extracted webhook
    try:
        from services.webhooks import fire_event
        from db.models import Document
        doc = await db.get(Document, uuid.UUID(document_id))
        if doc:
            await fire_event(
                db=db,
                project_id=project_id,
                event_type="entity.extracted",
                payload={
                    "project_id": project_id,
                    "document_id": document_id,
                    "entity_count": len(merged_entities),
                    "relationship_count": len(all_llm_relationships),
                },
            )
            await db.flush()
    except Exception:
        logger.warning("Failed to fire entity.extracted webhook")

    return len(merged_entities)
