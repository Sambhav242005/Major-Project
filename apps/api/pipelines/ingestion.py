"""Ingestion pipeline — parse → chunk → embed → extract entities.

Triggered as a background task after document upload.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Document, DocumentChunk
from services.documents import update_document_status
from pipelines.parser import parse_document
from pipelines.chunking import chunk_pages
from pipelines.embeddings import upsert_chunks

logger = logging.getLogger(__name__)


async def ingest_document(db: AsyncSession, document_id: str, file_content: bytes) -> None:
    """Run the full ingestion pipeline for a document.

    Stages:
    1. Parse → extract text pages
    2. Chunk → split into ~600-token segments
    3. Embed → upsert into ChromaDB
    4. Store chunk metadata in Postgres
    5. Extract entities and relationships
    6. Mark processed
    """
    try:
        doc = await db.get(Document, document_id)
        if not doc:
            logger.error(f"Document {document_id} not found")
            return

        # Stage 1: Update status to processing
        await update_document_status(db, document_id, "processing")
        await db.commit()

        # Stage 2: Parse document
        logger.info(f"Parsing {doc.filename}")
        pages = parse_document(file_content, doc.filename, doc.file_type)

        if not pages or all(not p.get("text", "").strip() for p in pages):
            await update_document_status(
                db, document_id, "failed",
                error_message="No text content could be extracted from the document"
            )
            await db.commit()
            return

        # Stage 3: Chunk text
        logger.info(f"Chunking {len(pages)} pages")
        chunks = chunk_pages(pages, max_tokens=600, overlap_tokens=80)

        if not chunks:
            await update_document_status(
                db, document_id, "failed",
                error_message="Document produced no chunks after processing"
            )
            await db.commit()
            return

        # Stage 4: Embed and upsert to ChromaDB
        logger.info(f"Embedding {len(chunks)} chunks")
        chroma_ids = upsert_chunks(
            chunks=chunks,
            project_id=str(doc.project_id),
            document_id=document_id,
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

        logger.info(f"Document {document_id} processed: {len(chunks)} chunks, {len(pages)} pages")

    except Exception as e:
        logger.exception(f"Ingestion failed for document {document_id}")
        try:
            await update_document_status(
                db, document_id, "failed",
                error_message=str(e)[:500]
            )
            await db.commit()
        except Exception:
            logger.exception(f"Failed to update status for {document_id}")
