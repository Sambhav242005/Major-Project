"""Agent tools — callable functions for LangGraph tool-calling nodes."""

import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Entity, EntityMention, Relationship, DocumentChunk, Document
from pipelines.embeddings import query_chunks

logger = logging.getLogger(__name__)

# Tool registry: name -> (description, function)
TOOL_REGISTRY: dict[str, dict] = {}


def register_tool(name: str, description: str, parameters: dict):
    """Decorator to register a tool for agent use."""
    def decorator(func):
        TOOL_REGISTRY[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "function": func,
        }
        return func
    return decorator


@register_tool(
    name="search_chunks",
    description="Search the knowledge base for relevant text chunks. Returns top results with source information.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "top_k": {"type": "integer", "description": "Number of results (default 5)"},
        },
        "required": ["query"],
    },
)
async def search_chunks_tool(query: str, top_k: int = 5, project_id: str = "", db=None, **kwargs) -> str:
    """Search ChromaDB for relevant chunks."""
    results = await query_chunks(query=query, project_id=project_id, top_k=top_k, db_session=db)
    if not results:
        return json.dumps({"results": [], "message": "No relevant chunks found."})

    formatted = []
    for i, r in enumerate(results, 1):
        formatted.append({
            "index": i,
            "text": r["text"][:500],
            "filename": r.get("filename", "unknown"),
            "page_number": r.get("page_number", 0),
            "score": round(r.get("score", 0), 3),
        })
    return json.dumps({"results": formatted})


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

    # Get relationships
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
    entity_map = {}
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


async def execute_tool(
    tool_name: str,
    arguments: dict,
    project_id: str = "",
    db=None,
) -> str:
    """Execute a registered tool by name."""
    if tool_name not in TOOL_REGISTRY:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    tool = TOOL_REGISTRY[tool_name]
    func = tool["function"]

    try:
        result = await func(
            project_id=project_id,
            db=db,
            **arguments,
        )
        return result
    except Exception as e:
        logger.error(f"Tool execution failed: {tool_name}: {e}")
        return json.dumps({"error": str(e)})


def get_tool_schemas() -> list[dict]:
    """Get OpenAI-style tool schemas for all registered tools."""
    schemas = []
    for name, tool in TOOL_REGISTRY.items():
        schemas.append({
            "type": "function",
            "function": {
                "name": name,
                "description": tool["description"],
                "parameters": tool["parameters"],
            },
        })
    return schemas
