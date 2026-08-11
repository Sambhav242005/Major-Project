import uuid
import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_project_id
from core.security import get_current_user, User
from core.errors import DocumentNotFoundError
from core.rate_limit import limiter
from core.security_utils import sanitize_filename
from db.session import get_db, async_session_factory
from db.models import Document
from schemas import (
    DocumentUploadResponse, DocumentListResponse, DocumentOut,
    DocumentStatusResponse,
)
from services import documents as doc_service
from pipelines.ingestion import ingest_document

router = APIRouter()

# In-memory subscribers for document processing SSE
_doc_subscribers: dict[str, list[asyncio.Queue]] = {}

# Strong references to running ingestion tasks so the event loop never
# garbage-collects a task mid-run (same pattern as core.task_queue).
_running_ingestions: set[asyncio.Task] = set()


def _start_ingestion(session_factory, document_id: str, file_content: bytes) -> None:
    """Launch document ingestion in background. Non-blocking."""
    task = asyncio.create_task(ingest_document(session_factory, document_id, file_content))
    _running_ingestions.add(task)

    def _done(t: asyncio.Task):
        _running_ingestions.discard(t)

    task.add_done_callback(_done)


def _notify_doc_subscribers(document_id: str, event: dict):
    """Push event to all SSE subscribers watching this document."""
    if document_id in _doc_subscribers:
        dead = []
        for q in _doc_subscribers[document_id]:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            _doc_subscribers[document_id].remove(q)

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
@limiter.limit("30/minute")
async def upload_document(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    project_id: str = Depends(get_project_id),
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

    # Queue background ingestion — run it as its own asyncio task. Starlette's
    # BackgroundTasks are dropped when the response flows through the
    # BaseHTTPMiddleware stack, which silently skipped ingestion (uploads
    # stayed "pending" forever). asyncio.create_task + strong ref matches
    # core.task_queue.start_agent_task and reliably survives.
    # Commit first so the background session (separate from this request's)
    # can see the row we just flushed.
    await db.commit()
    _start_ingestion(async_session_factory, result["id"], content)

    return DocumentUploadResponse(
        id=result["id"],
        filename=result["filename"],
        status="pending",
        message="Document uploaded and queued for processing",
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    docs = await doc_service.list_documents(db, project_id)
    return DocumentListResponse(
        documents=[DocumentOut(**d) for d in docs]
    )


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: str,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    doc = await doc_service.get_document(db, document_id, project_id)
    if not doc:
        raise DocumentNotFoundError()
    return DocumentOut(**doc)


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: str,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    status = await doc_service.get_document_status(db, document_id, project_id)
    if not status:
        raise DocumentNotFoundError()
    return DocumentStatusResponse(**status)


@router.get("/{document_id}/chunks")
async def get_document_chunks(
    document_id: str,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all chunks for a document (scoped to the resolved project)."""
    doc = await doc_service.get_document(db, document_id, project_id)
    if not doc:
        raise DocumentNotFoundError()
    chunks = await doc_service.get_document_chunks(db, document_id)
    return {"status": "ok", "data": chunks}


@router.get("/{document_id}/entities")
async def get_document_entities(
    document_id: str,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all entities extracted from a document (scoped to the resolved project)."""
    doc = await doc_service.get_document(db, document_id, project_id)
    if not doc:
        raise DocumentNotFoundError()
    entities = await doc_service.get_document_entities(db, document_id)
    return {"status": "ok", "data": entities}


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await doc_service.delete_document(db, document_id, project_id)
    if not deleted:
        raise DocumentNotFoundError()
    return {"deleted": True}


@router.post("/{document_id}/retry", status_code=202)
async def retry_document(
    document_id: str,
    request: Request,
    response: Response,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-trigger ingestion for a document stuck at pending/failed.

    The original file bytes aren't persisted (Supabase Storage is a TODO),
    so the client must re-submit the file as `file` in the multipart body.
    """
    form = await request.form()
    file = form.get("file")
    if file is None:
        raise HTTPException(
            status_code=400,
            detail="Re-upload the file to retry: POST /documents/{id}/retry with the file as multipart 'file'",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 25MB limit")

    # Only allow retrying pending/failed docs — a processed doc has no reason
    # to be reprocessed (delete + re-upload instead).
    status = await doc_service.get_document_status(db, document_id, project_id)
    if not status:
        raise DocumentNotFoundError()
    if status["status"] not in ("pending", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Document status is '{status['status']}'; only pending/failed documents can be retried",
        )

    # Clear any previous error, reset to pending, commit so the background
    # session can see it.
    doc = await db.get(Document, uuid.UUID(document_id))
    if doc:
        doc.status = "pending"
        doc.error_message = None
        await db.commit()

    _start_ingestion(async_session_factory, document_id, content)
    return {
        "id": document_id,
        "status": "pending",
        "message": "Document queued for reprocessing",
    }


@router.get("/{document_id}/stream")
async def stream_document_processing(
    document_id: str,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSE stream for real-time document processing status."""
    doc = await doc_service.get_document(db, document_id, project_id)
    if not doc:
        raise DocumentNotFoundError()
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    if document_id not in _doc_subscribers:
        _doc_subscribers[document_id] = []
    _doc_subscribers[document_id].append(q)

    async def event_stream():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30)
                    yield f"data: {json.dumps(event, default=str)}\n\n"
                    if event.get("stage") == "complete" or event.get("status") == "failed":
                        break
                except asyncio.TimeoutError:
                    yield f": keepalive\n\n"
        finally:
            if document_id in _doc_subscribers:
                _doc_subscribers[document_id] = [x for x in _doc_subscribers[document_id] if x is not q]

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# Wire up the ingestion notifier
from pipelines.ingestion import set_doc_notifier
set_doc_notifier(_notify_doc_subscribers)
