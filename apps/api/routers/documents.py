import uuid
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import get_current_user, User
from core.errors import DocumentNotFoundError, PermissionDeniedError
from core.security_utils import sanitize_filename
from db.session import get_db
from schemas import (
    DocumentUploadResponse, DocumentListResponse, DocumentOut,
    DocumentStatusResponse,
)
from services import documents as doc_service
from pipelines.ingestion import ingest_document

router = APIRouter()

ALLOWED_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
    "text/csv",
    "image/png",
    "image/jpeg",
    "image/tiff",
    "image/bmp",
    "image/webp",
}

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB


@router.post("", status_code=202, response_model=DocumentUploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate file type
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{file.content_type}' not allowed. Accepted: PDF, DOCX, TXT, images"
        )

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 25MB limit")

    # TODO: Get project_id from request/header (Phase 1 step: add project context)
    project_id = "00000000-0000-0000-0000-000000000001"  # placeholder

    # Generate storage path
    doc_id = str(uuid.uuid4())
    safe_filename = sanitize_filename(file.filename or "unnamed")
    storage_path = f"projects/{project_id}/documents/{doc_id}/{safe_filename}"

    # Insert document record
    result = await doc_service.upload_document(
        db=db,
        user=user,
        filename=safe_filename,
        file_type=file.content_type,
        storage_path=storage_path,
        project_id=project_id,
    )

    # TODO: Upload to Supabase Storage (Phase 1 step: add storage client)

    # Queue background ingestion
    background_tasks.add_task(ingest_document, db, result["id"], content)

    return DocumentUploadResponse(
        id=result["id"],
        filename=result["filename"],
        status="pending",
        message="Document uploaded and queued for processing",
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project_id = "00000000-0000-0000-0000-000000000001"  # placeholder
    docs = await doc_service.list_documents(db, project_id)
    return DocumentListResponse(
        documents=[DocumentOut(**d) for d in docs]
    )


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project_id = "00000000-0000-0000-0000-000000000001"  # placeholder
    doc = await doc_service.get_document(db, document_id, project_id)
    if not doc:
        raise DocumentNotFoundError()
    return DocumentOut(**doc)


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project_id = "00000000-0000-0000-0000-000000000001"  # placeholder
    status = await doc_service.get_document_status(db, document_id, project_id)
    if not status:
        raise DocumentNotFoundError()
    return DocumentStatusResponse(**status)


@router.get("/{document_id}/chunks")
async def get_document_chunks(
    document_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all chunks for a document."""
    chunks = await doc_service.get_document_chunks(db, document_id)
    return {"status": "ok", "data": chunks}


@router.get("/{document_id}/entities")
async def get_document_entities(
    document_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all entities extracted from a document."""
    entities = await doc_service.get_document_entities(db, document_id)
    return {"status": "ok", "data": entities}


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project_id = "00000000-0000-0000-0000-000000000001"  # placeholder
    deleted = await doc_service.delete_document(db, document_id, project_id)
    if not deleted:
        raise DocumentNotFoundError()
    return {"deleted": True}
