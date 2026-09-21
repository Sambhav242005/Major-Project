"""Entity extraction orchestration — DB persistence and webhook."""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Entity, EntityMention, Relationship
from pipelines.extraction.chunking import _extract_cohesive_chunks
from pipelines.extraction.llm_extract import _llm_extract
from pipelines.extraction.merge import _cooccurrence_relationships, _merge_entities
from pipelines.extraction.ner import _spacy_ner

logger = logging.getLogger(__name__)


async def extract_entities_from_chunks(
    db: AsyncSession,
    chunks: list[dict],
    project_id: str,
    document_id: str,
) -> int:
    """Extract entities and relationships from document chunks."""
    if not chunks:
        return 0

    all_spacy_entities = []
    for chunk in chunks:
        all_spacy_entities.extend(_spacy_ner(chunk.get("text", "")))

    batches = _extract_cohesive_chunks(chunks)
    all_llm_entities: list[dict] = []
    all_llm_relationships: list[dict] = []

    for batch in batches:
        result = await _llm_extract(batch["text"])
        all_llm_entities.extend(result["entities"])
        all_llm_relationships.extend(result["relationships"])

    merged_entities = _merge_entities(all_spacy_entities, all_llm_entities)

    if not all_llm_relationships:
        cooccurrence_names = {e["name"].lower().strip() for e in merged_entities if e["name"].strip()}
        all_llm_relationships = _cooccurrence_relationships(chunks, cooccurrence_names)
        if all_llm_relationships:
            logger.info(
                f"LLM returned no relationships; derived {len(all_llm_relationships)} "
                f"co-occurrence edges for document {document_id}"
            )

    entity_map: dict[str, str] = {}

    for ent in merged_entities:
        name = ent["name"]
        ent_type = ent["type"]
        name_lower = name.lower().strip()

        stmt = select(Entity).where(
            Entity.project_id == uuid.UUID(project_id),
            Entity.name.ilike(name),
            Entity.type == ent_type,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            entity_map[name_lower] = str(existing.id)
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

    for chunk in chunks:
        chunk_text = chunk.get("text", "")
        chunk_id = chunk.get("id")
        for ent in _spacy_ner(chunk_text):
            name_lower = ent["name"].lower().strip()
            if name_lower in entity_map:
                mention = EntityMention(
                    entity_id=uuid.UUID(entity_map[name_lower]),
                    document_id=uuid.UUID(document_id),
                    chunk_id=uuid.UUID(chunk_id) if chunk_id else None,
                    mention_text=ent["name"],
                    confidence=0.8,
                )
                db.add(mention)

    await db.flush()

    for rel in all_llm_relationships:
        source_name = rel.get("source", "").lower().strip()
        target_name = rel.get("target", "").lower().strip()

        if source_name in entity_map and target_name in entity_map:
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

    try:
        from db.models import Document
        from services.webhooks import fire_event

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
