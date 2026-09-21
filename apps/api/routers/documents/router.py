"""Documents endpoints — upload, list, status, chunks, entities, delete, retry, stream."""

import asyncio
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_project_id
from core.errors import DocumentNotFoundError
from core.rate_limit import limiter
from core.security import User, get_current_user
from core.security_utils import sanitize_filename
from core.sse import queue_sse_stream
from db.models import Document
from db.session import async_session_factory, get_db
from schemas import DocumentListResponse, DocumentOut, DocumentStatusResponse, DocumentUploadResponse
from services import documents as doc_service
from services.audit import write_audit_log
from .ingestion_tasks import _doc_subscribers, _start_ingestion
from .validation import ALLOWED_TYPES, MAX_FILE_SIZE

router = APIRouter()


@router.post("", status_code=202, response_model=DocumentUploadResponse)
@limiter.limit("30/minute")
async def upload_document(request: Request, response: Response, file: UploadFile = File(...), project_id: str = Depends(get_project_id), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"File type '{file.content_type}' not allowed. Accepted: PDF, DOCX, TXT, images")
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 25MB limit")
    doc_id = str(uuid.uuid4())
    safe_filename = sanitize_filename(file.filename or "unnamed")
    storage_path = f"projects/{project_id}/documents/{doc_id}/{safe_filename}"
    result = await doc_service.upload_document(db=db, user=user, filename=safe_filename, file_type=file.content_type, storage_path=storage_path, project_id=project_id)
    await write_audit_log(db=db, project_id=project_id, actor_id=user.id, action="document.uploaded", resource_type="document", resource_id=result["id"], meta={"filename": result["filename"]})
    await db.commit()
    _start_ingestion(async_session_factory, result["id"], content)
    return DocumentUploadResponse(id=result["id"], filename=result["filename"], status="pending", message="Document uploaded and queued for processing")


@router.get("", response_model=DocumentListResponse)
async def list_documents(project_id: str = Depends(get_project_id), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    docs = await doc_service.list_documents(db, project_id)
    return DocumentListResponse(documents=[DocumentOut(**d) for d in docs])


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(document_id: str, project_id: str = Depends(get_project_id), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    doc = await doc_service.get_document(db, document_id, project_id)
    if not doc:
        raise DocumentNotFoundError()
    return DocumentOut(**doc)


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(document_id: str, project_id: str = Depends(get_project_id), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    status = await doc_service.get_document_status(db, document_id, project_id)
    if not status:
        raise DocumentNotFoundError()
    return DocumentStatusResponse(**status)


@router.get("/{document_id}/chunks")
async def get_document_chunks(document_id: str, project_id: str = Depends(get_project_id), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    doc = await doc_service.get_document(db, document_id, project_id)
    if not doc:
        raise DocumentNotFoundError()
    chunks = await doc_service.get_document_chunks(db, document_id)
    return {"status": "ok", "data": chunks}


@router.get("/{document_id}/entities")
async def get_document_entities(document_id: str, project_id: str = Depends(get_project_id), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    doc = await doc_service.get_document(db, document_id, project_id)
    if not doc:
        raise DocumentNotFoundError()
    entities = await doc_service.get_document_entities(db, document_id)
    return {"status": "ok", "data": entities}


@router.delete("/{document_id}")
async def delete_document(document_id: str, project_id: str = Depends(get_project_id), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    deleted = await doc_service.delete_document(db, document_id, project_id)
    if not deleted:
        raise DocumentNotFoundError()
    await write_audit_log(db=db, project_id=project_id, actor_id=user.id, action="document.deleted", resource_type="document", resource_id=document_id)
    await db.commit()
    return {"deleted": True}


@router.post("/{document_id}/retry", status_code=202)
async def retry_document(document_id: str, request: Request, response: Response, project_id: str = Depends(get_project_id), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    form = await request.form()
    file = form.get("file")
    if file is None:
        raise HTTPException(status_code=400, detail="Re-upload the file to retry: POST /documents/{id}/retry with the file as multipart 'file'")
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 25MB limit")
    status = await doc_service.get_document_status(db, document_id, project_id)
    if not status:
        raise DocumentNotFoundError()
    if status["status"] not in ("pending", "failed"):
        raise HTTPException(status_code=409, detail=f"Document status is '{status['status']}'; only pending/failed documents can be retried")
    doc = await db.get(Document, uuid.UUID(document_id))
    if doc:
        doc.status = "pending"
        doc.error_message = None
        await db.commit()
    _start_ingestion(async_session_factory, document_id, content)
    return {"id": document_id, "status": "pending", "message": "Document queued for reprocessing"}


@router.get("/{document_id}/stream")
async def stream_document_processing(document_id: str, project_id: str = Depends(get_project_id), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    doc = await doc_service.get_document(db, document_id, project_id)
    if not doc:
        raise DocumentNotFoundError()
    def _subscribe():
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        if document_id not in _doc_subscribers:
            _doc_subscribers[document_id] = []
        _doc_subscribers[document_id].append(q)
        return q
    def _unsubscribe(q: asyncio.Queue):
        if document_id in _doc_subscribers:
            _doc_subscribers[document_id] = [x for x in _doc_subscribers[document_id] if x is not q]
    return await queue_sse_stream(subscribe=_subscribe, unsubscribe=_unsubscribe, done_condition=lambda e: e.get("stage") == "complete" or e.get("status") == "failed")
