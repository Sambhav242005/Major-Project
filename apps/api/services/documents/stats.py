"""Document stats — status filtering and counts."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Document


async def get_documents_by_status(db: AsyncSession, project_id: str, status: str) -> list[Document]:
    """Get all documents with a given status (for dashboard/pipeline)."""
    stmt = select(Document).where(
        Document.project_id == uuid.UUID(project_id),
        Document.status == status,
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def count_documents_by_status(db: AsyncSession, project_id: str) -> dict:
    """Count documents grouped by status."""
    stmt = (
        select(Document.status, func.count(Document.id))
        .where(Document.project_id == uuid.UUID(project_id))
        .group_by(Document.status)
    )
    result = await db.execute(stmt)
    counts = {"pending": 0, "processing": 0, "processed": 0, "failed": 0}
    for status, count in result.all():
        if status in counts:
            counts[status] = count
    return counts
