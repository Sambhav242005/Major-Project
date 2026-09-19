"""Ingestion pipeline body — parse → chunk → embed → extract → persist."""

import asyncio
import logging
import uuid
from datetime import datetime
from functools import partial

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Document, DocumentChunk
from pipelines.chunking import chunk_pages
from pipelines.embeddings import upsert_chunks
from pipelines.ingestion.notifier import _notify
from pipelines.parser import parse_document
from services.documents import update_document_status

logger = logging.getLogger(__name__)


async def _offload(fn, *args):
    """Run a blocking sync call off the event loop (thread pool)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(fn, *args))


async def _ingest_document_body(db: AsyncSession, document_id: str, file_content: bytes) -> None:
    """Run the full ingestion pipeline for a document (body — caller owns the session)."""
    try:
        doc = await db.get(Document, uuid.UUID(document_id))
        if not doc:
            logger.error(f"Document {document_id} not found")
            return

        await update_document_status(db, document_id, "processing")
        await db.commit()
        _notify(document_id, {"stage": "processing", "status": "running", "timestamp": datetime.utcnow().isoformat()})

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

        logger.info(f"Embedding {len(chunks)} chunks")
        _notify(document_id, {"stage": "embedding", "status": "running", "chunk_count": len(chunks), "timestamp": datetime.utcnow().isoformat()})
        chroma_ids = await _offload(
            upsert_chunks,
            chunks,
            str(doc.project_id),
            document_id,
        )

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

        await db.flush()

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
            logger.warning(f"Entity extraction failed for {document_id}: {e}")

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
