"""Document CRUD — upload, fetch, list, update, delete."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import User
from db.models import Document


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
    return _doc_to_dict(doc)


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
