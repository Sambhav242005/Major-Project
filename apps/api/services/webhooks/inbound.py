"""Webhook inbound — routing and handlers for inbound webhooks."""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import InboundWebhook
from core.outbound import validate_public_https_url
from .signing import verify_inbound_signature, MAX_PAYLOAD_SIZE

logger = logging.getLogger(__name__)


async def _finish_ingest_mutation(operation):
    """Finish persistence and job launch before returning caller cancellation."""
    task = asyncio.create_task(operation)
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        # Keep a strong reference and withstand repeated request cancellation.
        # A thread doing an atomic file replacement cannot safely be cancelled.
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        try:
            task.result()
        except Exception:
            logger.exception("Inbound ingestion persistence failed after cancellation")
        raise


async def handle_inbound(
    db: AsyncSession,
    slug: str,
    payload: bytes,
    headers: dict | None = None,
) -> dict:
    """Route an inbound webhook to its handler."""
    stmt = select(InboundWebhook).where(
        InboundWebhook.slug == slug,
        InboundWebhook.active == True,
    )
    result = await db.execute(stmt)
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    secret = (webhook.config or {}).get("secret")
    signature = (headers or {}).get("x-webhook-signature", "")
    if not isinstance(secret, str) or not secret or not verify_inbound_signature(payload, signature, secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    if len(payload) > MAX_PAYLOAD_SIZE:
        raise HTTPException(status_code=413, detail="Webhook payload exceeds maximum size")
    try:
        payload = json.loads(payload)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Webhook body must be JSON")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhook body must be a JSON object")

    handler = webhook.handler
    config = webhook.config or {}

    if handler == "ingest_document":
        return await _handle_ingest_document(db, webhook, payload, config)
    elif handler == "trigger_agent":
        return await _handle_trigger_agent(db, webhook, payload, config)
    elif handler == "mcp_receive":
        return await _handle_mcp_receive(db, webhook, payload, config)
    else:
        return {"error": f"Unknown handler: {handler}"}


async def _handle_ingest_document(
    db: AsyncSession,
    webhook: InboundWebhook,
    payload: dict,
    config: dict,
) -> dict:
    """Handle inbound document ingestion."""
    file_url = payload.get("file_url")
    filename = payload.get("filename", "webhook_upload")

    if not file_url:
        return {"error": "Missing file_url in payload"}

    try:
        from routers.documents.validation import ALLOWED_TYPES, MAX_FILE_SIZE, UploadValidationError, validate_upload
        await validate_public_https_url(file_url)
        async with asyncio.timeout(60), httpx.AsyncClient(timeout=60, follow_redirects=False, trust_env=False) as client:
            async with client.stream("GET", file_url) as resp:
                resp.raise_for_status()
                if resp.is_redirect:
                    raise ValueError("Document redirects are not allowed")
                file_type = resp.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if file_type not in ALLOWED_TYPES:
                    raise ValueError("Unsupported document content type")
                file_content = bytearray()
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    file_content.extend(chunk)
                    if len(file_content) > MAX_FILE_SIZE:
                        raise ValueError("Document exceeds 25MB limit")
                if not file_content:
                    raise ValueError("Empty document")
                try:
                    validate_upload(bytes(file_content), filename, file_type)
                except UploadValidationError as exc:
                    raise ValueError(f"Document rejected: {exc}") from exc
    except Exception as e:
        return {"error": f"Failed to download file: {e}"}

    from core.security_utils import sanitize_filename
    from db.models import Document
    from db.session import async_session_factory
    from services.documents.storage import save_original, delete_original
    from routers.documents.ingestion_tasks import _start_ingestion

    document_id = uuid.uuid4()
    filename = sanitize_filename(str(filename)) or "webhook_upload"
    doc = Document(id=document_id, project_id=webhook.project_id, filename=filename,
                   file_type=file_type, storage_path=f"projects/{webhook.project_id}/documents/{document_id}/{filename}",
                   status="pending")
    async def persist_and_launch():
        db.add(doc)
        try:
            await db.flush()
            await asyncio.to_thread(save_original, str(webhook.project_id), str(document_id), bytes(file_content))
            await db.commit()
        except Exception:
            for cleanup in (db.rollback(), asyncio.to_thread(delete_original, str(webhook.project_id), str(document_id))):
                try:
                    await cleanup
                except Exception:
                    logger.exception("Inbound document persistence cleanup failed")
            raise
        _start_ingestion(async_session_factory, str(document_id), bytes(file_content))

    await _finish_ingest_mutation(persist_and_launch())
    return {"status": "pending", "document_id": str(document_id), "filename": filename, "size": len(file_content)}


async def _handle_trigger_agent(
    db: AsyncSession,
    webhook: InboundWebhook,
    payload: dict,
    config: dict,
) -> dict:
    """Handle inbound agent trigger."""
    from services.agents import run_agent

    agent_id = payload.get("agent_id") or config.get("agent_id")
    input_data = payload.get("input", {})

    if not agent_id:
        return {"error": "Missing agent_id in payload or config"}

    result = await run_agent(
        db=db,
        agent_id=agent_id,
        project_id=str(webhook.project_id),
        input_data=input_data,
    )
    return result


async def _handle_mcp_receive(
    db: AsyncSession,
    webhook: InboundWebhook,
    payload: dict,
    config: dict,
) -> dict:
    """Handle MCP data reception — chunk and embed into knowledge base."""
    from db.models import Document, DocumentChunk
    from pipelines.chunking import chunk_pages
    from pipelines.embeddings import upsert_chunks

    data = payload.get("data", "")
    source = payload.get("source", "mcp_receiver")

    if not data:
        return {"error": "No data in payload"}

    doc = Document(
        id=uuid.uuid4(),
        project_id=webhook.project_id,
        filename=f"mcp_{source}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.txt",
        file_type="text/plain",
        storage_path=f"mcp://{source}",
        status="processing",
    )
    db.add(doc)
    await db.flush()

    pages = [{"text": data, "page_number": 1}]
    chunks = chunk_pages(pages, max_tokens=600, overlap_tokens=80)

    if chunks:
        chroma_ids = upsert_chunks(
            chunks=chunks,
            project_id=str(webhook.project_id),
            document_id=str(doc.id),
        )

        for i, chunk in enumerate(chunks):
            db_chunk = DocumentChunk(
                document_id=doc.id,
                chunk_index=chunk["chunk_index"],
                page_number=chunk.get("page_number"),
                text=chunk["text"],
                token_count=chunk["token_count"],
                chroma_id=chroma_ids[i] if i < len(chroma_ids) else f"{doc.id}_chunk_{i}",
            )
            db.add(db_chunk)

    doc.status = "processed"
    doc.processed_at = datetime.now(timezone.utc)
    await db.flush()

    return {"status": "ingested", "document_id": str(doc.id), "chunk_count": len(chunks)}
