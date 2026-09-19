"""Document content — chunks and entities for a document."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_document_chunks(db: AsyncSession, document_id: str) -> list[dict]:
    """Get all chunks for a document."""
    from db.models import DocumentChunk

    stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == uuid.UUID(document_id))
        .order_by(DocumentChunk.chunk_index)
    )
    result = await db.execute(stmt)
    chunks = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "chunk_index": c.chunk_index,
            "page_number": c.page_number,
            "text": c.text[:200] + "..." if len(c.text) > 200 else c.text,
            "token_count": c.token_count,
        }
        for c in chunks
    ]


async def get_document_entities(db: AsyncSession, document_id: str) -> list[dict]:
    """Get all entities extracted from a document."""
    from db.models import Entity, EntityMention

    stmt = (
        select(Entity)
        .join(EntityMention, EntityMention.entity_id == Entity.id)
        .where(EntityMention.document_id == uuid.UUID(document_id))
        .distinct()
    )
    result = await db.execute(stmt)
    entities = result.scalars().all()
    return [
        {
            "id": str(e.id),
            "name": e.name,
            "type": e.type,
            "description": e.description,
        }
        for e in entities
    ]
