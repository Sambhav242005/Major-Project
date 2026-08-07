"""Document ingestion service — upload, status tracking, deletion."""

import uuid
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import User
from db.models import Document


async def upload_document(
    db: AsyncSession,
    user: User,
    filename: str,
    file_type: str,
    storage_path: str,
    project_id: str,
) -> dict:
    """Insert document row with pending status."""
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        project_id=uuid.UUID(project_id),
        uploaded_by=uuid.UUID(user.id),
        filename=filename,
        file_type=file_type,
        storage_path=storage_path,
        status="pending",
        uploaded_at=datetime.utcnow(),
    )
    db.add(doc)
    await db.flush()
    return {"id": str(doc_id), "filename": filename, "status": "pending"}


async def get_document(db: AsyncSession, document_id: str, project_id: str) -> dict | None:
    """Fetch a single document by ID within a project."""
    stmt = select(Document).where(
        Document.id == uuid.UUID(document_id),
        Document.project_id == uuid.UUID(project_id),
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        return None
    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "file_type": doc.file_type,
        "status": doc.status,
        "page_count": doc.page_count,
        "error_message": doc.error_message,
        "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
    }


async def list_documents(db: AsyncSession, project_id: str) -> list[dict]:
    """List all documents for a project, newest first."""
    stmt = (
        select(Document)
        .where(Document.project_id == uuid.UUID(project_id))
        .order_by(Document.uploaded_at.desc())
    )
    result = await db.execute(stmt)
    docs = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "filename": d.filename,
            "file_type": d.file_type,
            "status": d.status,
            "page_count": d.page_count,
            "error_message": d.error_message,
            "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
            "processed_at": d.processed_at.isoformat() if d.processed_at else None,
        }
        for d in docs
    ]


async def get_document_status(db: AsyncSession, document_id: str, project_id: str) -> dict | None:
    """Get document processing status."""
    stmt = select(Document).where(
        Document.id == uuid.UUID(document_id),
        Document.project_id == uuid.UUID(project_id),
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        return None
    return {
        "id": str(doc.id),
        "status": doc.status,
        "error_message": doc.error_message,
    }


async def update_document_status(
    db: AsyncSession,
    document_id: str,
    status: str,
    error_message: str | None = None,
    page_count: int | None = None,
) -> None:
    """Update document status (called by ingestion pipeline)."""
    stmt = select(Document).where(Document.id == uuid.UUID(document_id))
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    if doc:
        doc.status = status
        if error_message is not None:
            doc.error_message = error_message
        if page_count is not None:
            doc.page_count = page_count
        if status == "processed":
            doc.processed_at = datetime.utcnow()
        await db.flush()


async def delete_document(db: AsyncSession, document_id: str, project_id: str) -> bool:
    """Delete a document and its chunks."""
    stmt = select(Document).where(
        Document.id == uuid.UUID(document_id),
        Document.project_id == uuid.UUID(project_id),
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        return False
    await db.delete(doc)
    await db.flush()
    return True


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
