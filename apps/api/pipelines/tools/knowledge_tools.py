"""Knowledge tools — entity lookup and document chunk retrieval."""

import json
import uuid

from sqlalchemy import select

from db.models import DocumentChunk, Entity, Relationship
from pipelines.tools.registry import register_tool


@register_tool(
    name="get_entity",
    description="Get details about a specific entity including its relationships.",
    parameters={
        "type": "object",
        "properties": {
            "entity_name": {"type": "string", "description": "Name of the entity to look up"},
        },
        "required": ["entity_name"],
    },
)
async def get_entity_tool(entity_name: str, project_id: str = "", db=None, **kwargs) -> str:
    """Get entity details and relationships."""
    if not db:
        return json.dumps({"error": "Database session not available"})

    stmt = select(Entity).where(
        Entity.project_id == uuid.UUID(project_id),
        Entity.name.ilike(f"%{entity_name}%"),
    )
    result = await db.execute(stmt)
    entities = result.scalars().all()

    if not entities:
        return json.dumps({"error": f"Entity '{entity_name}' not found"})

    entity = entities[0]

    rel_stmt = select(Relationship).where(
        (Relationship.source_entity_id == entity.id) | (Relationship.target_entity_id == entity.id)
    )
    rel_result = await db.execute(rel_stmt)
    relationships = rel_result.scalars().all()

    rels = []
    for r in relationships:
        other_id = r.target_entity_id if r.source_entity_id == entity.id else r.source_entity_id
        other_stmt = select(Entity).where(Entity.id == other_id)
        other_result = await db.execute(other_stmt)
        other = other_result.scalar_one_or_none()
        if other:
            rels.append({
                "relation_type": r.relation_type,
                "connected_to": other.name,
                "connected_type": other.type,
                "description": r.description,
            })

    return json.dumps({
        "name": entity.name,
        "type": entity.type,
        "description": entity.description,
        "relationships": rels,
    })


@register_tool(
    name="get_document_chunks",
    description="Get all chunks from a specific document.",
    parameters={
        "type": "object",
        "properties": {
            "document_id": {"type": "string", "description": "UUID of the document"},
        },
        "required": ["document_id"],
    },
)
async def get_document_chunks_tool(document_id: str, db=None, **kwargs) -> str:
    """Get all chunks from a document."""
    if not db:
        return json.dumps({"error": "Database session not available"})

    stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == uuid.UUID(document_id))
        .order_by(DocumentChunk.chunk_index)
    )
    result = await db.execute(stmt)
    chunks = result.scalars().all()

    if not chunks:
        return json.dumps({"chunks": [], "message": "No chunks found for this document."})

    formatted = []
    for c in chunks:
        formatted.append({
            "chunk_index": c.chunk_index,
            "page_number": c.page_number,
            "text": c.text[:500],
            "token_count": c.token_count,
        })

    return json.dumps({"chunks": formatted, "total": len(formatted)})
