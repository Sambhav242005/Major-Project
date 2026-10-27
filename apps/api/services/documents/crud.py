"""Document CRUD — upload, fetch, list, update, delete."""

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import _user_uuid
from core.security import User
from db.models import Document, DocumentChunk, DocumentSource, Entity, EntityMention, Relationship


def _doc_to_dict(d: Document) -> dict:
    return {
        "id": str(d.id),
        "filename": d.filename,
        "file_type": d.file_type,
        "status": d.status,
        "page_count": d.page_count,
        "error_message": d.error_message,
        "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
        "processed_at": d.processed_at.isoformat() if d.processed_at else None,
    }


async def upload_document(
    db: AsyncSession,
    user: User,
    filename: str,
    file_type: str,
    storage_path: str,
    project_id: str,
    document_id: str | None = None,
) -> dict:
    """Insert document row with pending status."""
    doc_id = uuid.UUID(document_id) if document_id else uuid.uuid4()
    doc = Document(
        id=doc_id,
        project_id=uuid.UUID(project_id),
        uploaded_by=_user_uuid(user.id),
        filename=filename,
        file_type=file_type,
        storage_path=storage_path,
        status="pending",
        uploaded_at=datetime.now(timezone.utc),
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
    return _doc_to_dict(doc)


async def lock_document_for_mutation(db: AsyncSession, document_id: str, project_id: str) -> Document | None:
    """Serialize retry/delete through commit on PostgreSQL and SQLite.

    A no-op UPDATE takes a writer lock on SQLite, where SELECT FOR UPDATE is
    ignored. RETURNING reads the current status after the lock is acquired.
    """
    try:
        identifier, project = uuid.UUID(document_id), uuid.UUID(project_id)
    except (ValueError, TypeError):
        return None
    result = await db.execute(
        update(Document)
        .where(Document.id == identifier, Document.project_id == project)
        .values(status=Document.status)
        .returning(Document)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def list_documents(db: AsyncSession, project_id: str, limit: int = 100, offset: int = 0) -> list[dict]:
    """List all documents for a project, newest first."""
    stmt = (
        select(Document)
        .where(Document.project_id == uuid.UUID(project_id))
        .order_by(Document.uploaded_at.desc())
        .limit(min(limit, 100))
        .offset(max(offset, 0))
    )
    result = await db.execute(stmt)
    docs = result.scalars().all()
    return [_doc_to_dict(d) for d in docs]


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
            doc.processed_at = datetime.now(timezone.utc)
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
    # Remove external evidence first: a failed vector deletion must not leave a
    # successfully deleted SQL document still retrievable by chat.
    from pipelines.embeddings import delete_document_chunks
    await asyncio.to_thread(delete_document_chunks, document_id)
    await db.execute(delete(EntityMention).where(EntityMention.document_id == doc.id))
    await db.execute(delete(Relationship).where(Relationship.source_document_id == doc.id))
    await db.execute(update(Entity).where(Entity.first_seen_document_id == doc.id).values(first_seen_document_id=None))
    await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
    await db.execute(delete(DocumentSource).where(DocumentSource.document_id == doc.id))
    await db.delete(doc)
    await db.flush()
    return True
