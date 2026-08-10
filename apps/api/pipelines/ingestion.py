"""Ingestion pipeline — parse → chunk → embed → extract entities.

Triggered as a background task after document upload.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from functools import partial

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Document, DocumentChunk
from services.documents import update_document_status
from pipelines.parser import parse_document
from pipelines.chunking import chunk_pages
from pipelines.embeddings import upsert_chunks

logger = logging.getLogger(__name__)

# SSE notification callback (set by documents router)
_notify_doc = None


def set_doc_notifier(notifier):
    global _notify_doc
    _notify_doc = notifier


def _notify(document_id: str, event: dict):
    if _notify_doc:
        _notify_doc(document_id, event)


async def _offload(fn, *args):
    """Run a blocking sync call off the event loop (thread pool).

    parse_document, chunk_pages, and upsert_chunks are CPU/IO-bound sync
    calls that would stall the whole loop if awaited inline.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(fn, *args))


async def _ingest_document_body(db: AsyncSession, document_id: str, file_content: bytes) -> None:
    """Run the full ingestion pipeline for a document (body — caller owns the session).

    Stages:
    1. Parse → extract text pages
    2. Chunk → split into ~600-token segments
    3. Embed → upsert into ChromaDB
    4. Store chunk metadata in Postgres
    5. Extract entities and relationships
    6. Mark processed
    """
    try:
        doc = await db.get(Document, uuid.UUID(document_id))
        if not doc:
            logger.error(f"Document {document_id} not found")
            return

        # Stage 1: Update status to processing
        await update_document_status(db, document_id, "processing")
        await db.commit()
        _notify(document_id, {"stage": "processing", "status": "running", "timestamp": datetime.utcnow().isoformat()})

        # Stage 2: Parse document (off the event loop)
        logger.info(f"Parsing {doc.filename}")
        _notify(document_id, {"stage": "parsing", "status": "running", "timestamp": datetime.utcnow().isoformat()})
        pages = await _offload(parse_document, file_content, doc.filename, doc.file_type)

        if not pages or all(not p.get("text", "").strip() for p in pages):
            await update_document_status(
                db, document_id, "failed",
                error_message="No text content could be extracted from the document"
            )
            await db.commit()
            return

        # Stage 3: Chunk text (off the event loop)
        logger.info(f"Chunking {len(pages)} pages")
        _notify(document_id, {"stage": "chunking", "status": "running", "page_count": len(pages), "timestamp": datetime.utcnow().isoformat()})
        chunks = await _offload(chunk_pages, pages, 600, 80)

        if not chunks:
            await update_document_status(
                db, document_id, "failed",
                error_message="Document produced no chunks after processing"
            )
            await db.commit()
            return

        # Stage 4: Embed and upsert to ChromaDB (off the event loop — sync httpx)
        logger.info(f"Embedding {len(chunks)} chunks")
        _notify(document_id, {"stage": "embedding", "status": "running", "chunk_count": len(chunks), "timestamp": datetime.utcnow().isoformat()})
        chroma_ids = await _offload(
            upsert_chunks,
            chunks,
            str(doc.project_id),
            document_id,
        )

        # Stage 5: Store chunk metadata in Postgres + flush to get IDs
        db_chunks = []
        for i, chunk in enumerate(chunks):
            db_chunk = DocumentChunk(
                document_id=doc.id,
                chunk_index=chunk["chunk_index"],
                page_number=chunk.get("page_number"),
                text=chunk["text"],
                token_count=chunk["token_count"],
                chroma_id=chroma_ids[i] if i < len(chroma_ids) else f"{document_id}_chunk_{i}",
            )
            db.add(db_chunk)
            db_chunks.append(db_chunk)

        await db.flush()  # Flush to generate IDs before entity extraction

        # Stage 6: Extract entities and relationships
        logger.info(f"Extracting entities from {len(chunks)} chunks")
        _notify(document_id, {"stage": "extracting_entities", "status": "running", "timestamp": datetime.utcnow().isoformat()})
        try:
            from pipelines.entity_extraction import extract_entities_from_chunks

            chunk_data = [
                {
                    "id": str(c.id),
                    "text": c.text,
                    "chunk_index": c.chunk_index,
                    "page_number": c.page_number,
                }
                for c in db_chunks
            ]

            entity_count = await extract_entities_from_chunks(
                db=db,
                chunks=chunk_data,
                project_id=str(doc.project_id),
                document_id=document_id,
            )
            logger.info(f"Extracted {entity_count} entities")
        except Exception as e:
            # Entity extraction failure is non-fatal — document is still processed
            logger.warning(f"Entity extraction failed for {document_id}: {e}")

        # Stage 7: Update document status
        await update_document_status(
            db, document_id, "processed",
            page_count=len(pages),
        )
        await db.commit()

        _notify(document_id, {
            "stage": "complete", "status": "completed",
            "chunk_count": len(chunks), "page_count": len(pages),
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Fire document.processed webhook
        try:
            from services.webhooks import fire_event
            await fire_event(
                db=db,
                project_id=str(doc.project_id),
                event_type="document.processed",
                payload={
                    "doc_id": document_id,
                    "filename": doc.filename,
                    "status": "processed",
                    "chunk_count": len(chunks),
                    "page_count": len(pages),
                },
            )
            await db.commit()
        except Exception:
            logger.warning("Failed to fire document.processed webhook")

        logger.info(f"Document {document_id} processed: {len(chunks)} chunks, {len(pages)} pages")

    except Exception as e:
        logger.exception(f"Ingestion failed for document {document_id}")
        try:
            await update_document_status(
                db, document_id, "failed",
                error_message=str(e)[:500]
            )
            await db.commit()

            # Fire document.failed webhook
            try:
                from services.webhooks import fire_event
                doc = await db.get(Document, uuid.UUID(document_id))
                if doc:
                    await fire_event(
                        db=db,
                        project_id=str(doc.project_id),
                        event_type="document.failed",
                        payload={
                            "doc_id": document_id,
                            "filename": doc.filename,
                            "error_message": str(e)[:500],
                        },
                    )
                    await db.commit()
            except Exception:
                logger.warning("Failed to fire document.failed webhook")
        except Exception:
            logger.exception(f"Failed to update status for {document_id}")


async def ingest_document(session_factory, document_id: str, file_content: bytes) -> None:
    """Run the full ingestion pipeline for a document.

    Opens its own DB session so the work survives after the request's
    dependency session is closed — Starlette runs background tasks after
    dependency teardown, so passing the request's `db` (the old behaviour)
    left `ingest_document` operating on a closed session and uploads stuck
    at "pending". Mirrors the pattern in core/task_queue.start_agent_task.
    """
    async with session_factory() as db:
        await _ingest_document_body(db, document_id, file_content)
