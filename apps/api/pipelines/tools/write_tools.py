"""Write tools — store entities and relationships."""

import json
import uuid

from sqlalchemy import select

from db.models import Entity, Relationship
from pipelines.tools.registry import register_tool


@register_tool(
    name="store_entities",
    description="Store extracted entities and relationships in the knowledge base.",
    parameters={
        "type": "object",
        "properties": {
            "entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string"},
                        "description": {"type": "string"},
                    },
                },
            },
            "relationships": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string"},
                        "target": {"type": "string"},
                        "relation_type": {"type": "string"},
                        "description": {"type": "string"},
                    },
                },
            },
        },
        "required": ["entities"],
    },
)
async def store_entities_tool(
    entities: list[dict],
    relationships: list[dict] = None,
    project_id: str = "",
    document_id: str = "",
    db=None,
    **kwargs,
) -> str:
    """Store entities and relationships in the database."""
    if not db:
        return json.dumps({"error": "Database session not available"})

    relationships = relationships or []
    entity_map: dict[str, str] = {}
    stored_count = 0

    for ent in entities:
        name = ent.get("name", "").strip()
        ent_type = ent.get("type", "other")
        if not name:
            continue

        stmt = select(Entity).where(
            Entity.project_id == uuid.UUID(project_id),
            Entity.name.ilike(name),
            Entity.type == ent_type,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            entity_map[name.lower()] = str(existing.id)
            if ent.get("description") and not existing.description:
                existing.description = ent["description"]
                await db.flush()
        else:
            new_entity = Entity(
                project_id=uuid.UUID(project_id),
                name=name,
                type=ent_type,
                description=ent.get("description", ""),
                first_seen_document_id=uuid.UUID(document_id) if document_id else None,
            )
            db.add(new_entity)
            await db.flush()
            entity_map[name.lower()] = str(new_entity.id)
            stored_count += 1

    rel_stored = 0
    for rel in relationships:
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
                    source_document_id=uuid.UUID(document_id) if document_id else None,
                )
                db.add(new_rel)
                rel_stored += 1

    await db.flush()

    return json.dumps({
        "entities_stored": stored_count,
        "relationships_stored": rel_stored,
        "total_entities_in_map": len(entity_map),
    })
