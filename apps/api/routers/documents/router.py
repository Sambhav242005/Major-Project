"""Documents endpoints — upload, list, status, chunks, entities, delete, retry, stream."""

import asyncio
import logging
import uuid
from urllib.parse import quote
from contextlib import aclosing
from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_project_id
from core.errors import DocumentNotFoundError
from core.rate_limit import limiter
from core.security import User, get_current_user
from core.security_utils import sanitize_filename
from core.sse import format_sse, KEEPALIVE_TIMEOUT
from starlette.responses import StreamingResponse
from db.session import async_session_factory, get_db
from schemas import DocumentListResponse, DocumentOut, DocumentStatusResponse, DocumentUploadResponse
from services import documents as doc_service
from services.documents.storage import save_original, load_original, delete_original
from services.audit import write_audit_log
from .ingestion_tasks import _doc_subscribers, _start_ingestion
from .validation import ALLOWED_TYPES, MAX_FILE_SIZE, ACCEPTED_SUMMARY, DOCUMENT_MAX_BYTES, IMAGE_MAX_BYTES, SUPPORTED_FORMATS, UploadValidationError, validate_upload

router = APIRouter()
logger = logging.getLogger(__name__)


async def _finish_mutation(operation):
    """Finish storage/SQL changes before request cancellation closes the session."""
    task = asyncio.create_task(operation)
    cancellation = None
    while True:
        try:
            result = await asyncio.shield(task)
            break
        except asyncio.CancelledError as exc:
            cancellation = exc
            if task.done():
                if not task.cancelled():
                    try:
                        task.result()
                    except Exception:
                        logger.exception("Document mutation failed during request cancellation")
                break
        except Exception:
            if cancellation is None:
                raise
            logger.exception("Document mutation failed during request cancellation")
            break
    if cancellation is not None:
        # Repeated caller cancellation must not stop a threaded filesystem write,
        # its compensation, or the commit followed by ingestion launch.
        raise cancellation
    return result


async def _compensate(operation):
    """Attempt every recovery step without masking the triggering failure."""
    try:
        await operation
    except Exception:
        logger.exception("Document mutation recovery failed")


def _recovery_state(doc):
    return doc.status, doc.processed_at, doc.error_message, doc.mutation_version


async def _recover_original(db, document_id, project_id, original, expected_state, *, evidence_removed=False):
    # Rollback released the previous writer lock. Another delete or retry may
    # already have won; reacquire before touching either bytes or metadata.
    doc = await doc_service.lock_document_for_mutation(db, document_id, project_id)
    if doc is None or doc.status in ("pending", "processing") or _recovery_state(doc) != expected_state:
        return
    if original is None:
        await asyncio.to_thread(delete_original, project_id, document_id)
    else:
        await asyncio.to_thread(save_original, project_id, document_id, original)
    if evidence_removed:
        doc.status = "failed"
        doc.processed_at = None
        doc.error_message = "Deletion was interrupted after evidence cleanup. Retry this document to restore searchable evidence from its original file."
    doc.mutation_version = (doc.mutation_version or 0) + 1
    # Keep the lock through the filesystem restoration and its SQL state update.
    await db.commit()


@router.post("", status_code=202, response_model=DocumentUploadResponse)
@limiter.limit("30/minute")
async def upload_document(request: Request, response: Response, file: UploadFile = File(...), project_id: str = Depends(get_project_id), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    content = await file.read()
    try:
        validate_upload(content, file.filename, file.content_type)
    except UploadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    doc_id = str(uuid.uuid4())
    safe_filename = sanitize_filename(file.filename or "unnamed")
    storage_path = f"projects/{project_id}/documents/{doc_id}/{safe_filename}"
    result = await doc_service.upload_document(db=db, user=user, filename=safe_filename, file_type=file.content_type, storage_path=storage_path, project_id=project_id, document_id=doc_id)
    async def _persist():
        try:
            await write_audit_log(db=db, project_id=project_id, actor_id=user.id, action="document.uploaded", resource_type="document", resource_id=result["id"], meta={"filename": result["filename"]})
            await asyncio.to_thread(save_original, project_id, result["id"], content)
            await db.commit()
        except Exception:
            await _compensate(db.rollback())
            await _compensate(asyncio.to_thread(delete_original, project_id, result["id"]))
            raise
        _start_ingestion(async_session_factory, result["id"], content)
    await _finish_mutation(_persist())
    return DocumentUploadResponse(id=result["id"], filename=result["filename"], status="pending", message="Document uploaded and queued for processing")


# Registered before the parametrized /{document_id} routes on purpose.
@router.get("/formats")
async def list_supported_formats(user: User = Depends(get_current_user)):
    """Machine-readable inventory of accepted knowledge-source formats (TODO 2.26 Phase 1)."""
    return {
        "accepted_summary": ACCEPTED_SUMMARY,
        "max_document_bytes": DOCUMENT_MAX_BYTES,
        "max_image_bytes": IMAGE_MAX_BYTES,
        "formats": [
            {
                "content_type": fmt.content_type,
                "label": fmt.label,
                "category": fmt.category,
                "max_bytes": fmt.max_bytes,
                "inline_preview": fmt.inline_preview,
            }
            for fmt in SUPPORTED_FORMATS
        ],
        "not_yet_supported": [
            {
                "category": "audio",
                "message": "Audio is not searchable project knowledge yet. Use the Meetings page to transcribe and analyze meeting audio.",
            },
            {
                "category": "video",
                "message": "Video ingestion with time citations is planned for a later release.",
            },
        ],
    }


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


@router.get("/{document_id}/original")
async def get_document_original(document_id: str, download: bool = True, project_id: str = Depends(get_project_id), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Authorize using metadata, never by accepting a storage path from a caller.
    try:
        uuid.UUID(document_id)
    except ValueError:
        raise DocumentNotFoundError()
    doc = await doc_service.get_document(db, document_id, project_id)
    if not doc:
        raise DocumentNotFoundError()
    try:
        content = await asyncio.to_thread(load_original, project_id, document_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Original file unavailable for this document")
    file_type = doc["file_type"]
    # Never render uploaded active formats in the application's origin; the
    # upload registry drives the inline-preview allowlist.
    preview_types = {fmt.content_type for fmt in SUPPORTED_FORMATS if fmt.inline_preview}
    if file_type in {"text/markdown", "text/csv"}:
        file_type = "text/plain"
    disposition = "inline" if not download and file_type in preview_types else "attachment"
    filename = quote(sanitize_filename(doc["filename"]) or "document", safe="")
    return Response(content, media_type=file_type, headers={
        "Content-Disposition": f"{disposition}; filename*=utf-8''{filename}",
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "sandbox; default-src 'none'",
    })


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
    doc = await doc_service.lock_document_for_mutation(db, document_id, project_id)
    if doc is None:
        raise DocumentNotFoundError()
    if doc.status in ("pending", "processing"):
        raise HTTPException(status_code=409, detail="Wait for processing to finish before deleting this document")
    recovery_state = _recovery_state(doc)
    async def _delete():
        original = None
        evidence_removal_started = False
        try:
            try:
                original = await asyncio.to_thread(load_original, project_id, document_id)
            except FileNotFoundError:
                pass  # Older uploads may have no saved original.
            # Detect a storage failure before removing searchable vector evidence.
            await asyncio.to_thread(delete_original, project_id, document_id)
            evidence_removal_started = True
            deleted = await doc_service.delete_document(db, document_id, project_id)
            if not deleted:
                raise DocumentNotFoundError()
            await write_audit_log(db=db, project_id=project_id, actor_id=user.id, action="document.deleted", resource_type="document", resource_id=document_id)
            await db.commit()
        except Exception:
            await _compensate(db.rollback())
            if original is not None or evidence_removal_started:
                # SQL rollback cannot restore vectors already removed externally.
                # Restore only if no newer mutation won the released row lock.
                await _compensate(_recover_original(db, document_id, project_id, original, recovery_state, evidence_removed=evidence_removal_started))
            raise
    await _finish_mutation(_delete())
    return {"deleted": True}


@router.post("/{document_id}/retry", status_code=202)
async def retry_document(document_id: str, request: Request, response: Response, project_id: str = Depends(get_project_id), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    doc = await doc_service.lock_document_for_mutation(db, document_id, project_id)
    if doc is None:
        raise DocumentNotFoundError()
    if doc.status != "failed":
        raise HTTPException(status_code=409, detail="Only failed documents can be retried")
    recovery_state = _recovery_state(doc)
    form = await request.form()
    file = form.get("file")
    if file is None:
        try:
            content = await asyncio.to_thread(load_original, project_id, document_id)
        except FileNotFoundError:
            raise HTTPException(status_code=400, detail="Original file unavailable for this older upload; re-upload the file as multipart 'file'")
    else:
        if not hasattr(file, "read") or file.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail="Unsupported retry file")
        if file.content_type != doc.file_type:
            raise HTTPException(status_code=400, detail="Retry file must use the original document type")
        content = await file.read()
        try:
            validate_upload(content, getattr(file, "filename", None), file.content_type)
        except UploadValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not content:
        raise HTTPException(status_code=400, detail="Empty document")
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 25MB limit")
    # File-free retries keep the durable original unchanged. A supplied replacement
    # is restored if the metadata transaction fails.
    async def _retry():
        previous = None
        if file is not None:
            try:
                previous = await asyncio.to_thread(load_original, project_id, document_id)
            except FileNotFoundError:
                pass
        try:
            if file is not None:
                await asyncio.to_thread(save_original, project_id, document_id, content)
            doc.status = "pending"
            doc.mutation_version = (doc.mutation_version or 0) + 1
            doc.error_message = None
            doc.processed_at = None
            await db.commit()
        except Exception:
            await _compensate(db.rollback())
            if file is not None:
                await _compensate(_recover_original(db, document_id, project_id, previous, recovery_state))
            raise
        _start_ingestion(async_session_factory, document_id, content)
    await _finish_mutation(_retry())
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
            if not _doc_subscribers[document_id]:
                _doc_subscribers.pop(document_id, None)

    async def events():
        # Subscribe first. A completion committed while the snapshot is being
        # read is either visible in that snapshot or already waiting in q.
        # Use a short new session rather than the request's earlier transaction.
        q = _subscribe()
        try:
            async with async_session_factory() as snapshot_db:
                current = await doc_service.get_document_status(snapshot_db, document_id, project_id)
            if current is None:
                yield {"stage": "failed", "status": "failed", "error_message": "Document is no longer available"}
                return
            if current["status"] == "processed":
                yield {"stage": "complete", "status": "completed"}
                return
            if current["status"] == "failed":
                yield {"stage": "failed", "status": "failed", "error_message": current.get("error_message")}
                return
            yield {"stage": current["status"], "status": "running"}
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=KEEPALIVE_TIMEOUT)
                except asyncio.TimeoutError:
                    yield {"step": "keepalive"}
                    continue
                yield event
                if event.get("stage") == "complete" or event.get("status") == "failed":
                    return
        finally:
            _unsubscribe(q)

    async def encoded_events():
        async with aclosing(events()) as stream:
            async for event in stream:
                yield format_sse(event)

    return StreamingResponse(encoded_events(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no",
    })
