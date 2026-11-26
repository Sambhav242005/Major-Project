"""Chat retrieval — entity context, graph expansion, source formatting."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import DocumentChunk, Entity, EntityMention


async def _get_entity_context(
    db: AsyncSession,
    project_id: str,
    chunk_ids: list[str],
) -> list[dict]:
    """Get entities mentioned in retrieved chunks for graph expansion.

    chunk_ids are Chroma IDs (e.g. "{document_id}_chunk_{n}") from
    query_chunks — map them to real DB chunk UUIDs before querying mentions,
    otherwise uuid.UUID() explodes on the compound id.
    """
    chroma_ids = [cid for cid in chunk_ids if cid]
    if not chroma_ids:
        return []

    # Map Chroma IDs -> DB chunk UUIDs
    chunk_stmt = select(DocumentChunk.id).where(DocumentChunk.chroma_id.in_(chroma_ids))
    chunk_result = await db.execute(chunk_stmt)
    db_chunk_ids = [row[0] for row in chunk_result.all()]

    if not db_chunk_ids:
        return []

    # Find entities that appear in these chunks
    stmt = select(EntityMention).where(EntityMention.chunk_id.in_(db_chunk_ids))
    result = await db.execute(stmt)
    mentions = result.scalars().all()

    entity_ids = list(set(m.entity_id for m in mentions))

    if not entity_ids:
        return []

    # Get entity details
    ent_stmt = select(Entity).where(Entity.id.in_(entity_ids))
    ent_result = await db.execute(ent_stmt)
    entities = ent_result.scalars().all()

    return [
        {
            "id": str(e.id),
            "name": e.name,
            "type": e.type,
            "description": e.description,
        }
        for e in entities
    ]


async def _expand_via_graph(
    db: AsyncSession,
    project_id: str,
    entity_ids: list[str],
    depth: int = 1,
) -> list[dict]:
    """Expand entity context via graph relationships (1 hop)."""
    from db.models import Relationship

    if not entity_ids:
        return []

    entity_uuids = [uuid.UUID(eid) for eid in entity_ids if eid]

    # Get relationships involving these entities (scoped to this project)
    stmt = select(Relationship).where(
        Relationship.project_id == uuid.UUID(project_id),
        (Relationship.source_entity_id.in_(entity_uuids))
        | (Relationship.target_entity_id.in_(entity_uuids))
    )
    result = await db.execute(stmt)
    relationships = result.scalars().all()

    # Collect neighboring entity IDs
    neighbor_ids = set()
    for rel in relationships:
        if str(rel.source_entity_id) not in entity_ids:
            neighbor_ids.add(rel.source_entity_id)
        if str(rel.target_entity_id) not in entity_ids:
            neighbor_ids.add(rel.target_entity_id)

    if not neighbor_ids:
        return []

    # Get neighbor entity details
    ent_stmt = select(Entity).where(Entity.id.in_(neighbor_ids))
    ent_result = await db.execute(ent_stmt)
    neighbors = ent_result.scalars().all()

    return [
        {
            "id": str(e.id),
            "name": e.name,
            "type": e.type,
            "description": e.description,
        }
        for e in neighbors
    ]


def _format_source_block(
    index: int,
    text: str,
    filename: str,
    page_number: int,
    doc_id: str,
) -> str:
    """Format a source block for the LLM prompt."""
    header = f"[Source {index}] Document: {filename}, Page: {page_number or 'N/A'}"
    return f"{header}\n{text[:800]}"  # Truncate long chunks
