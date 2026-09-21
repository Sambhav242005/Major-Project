"""Knowledge search — semantic search over ingested chunks."""

import logging
import uuid as _uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Document, DocumentChunk
from pipelines.embeddings import query_chunks

logger = logging.getLogger(__name__)


def _uuid_val(val: str) -> _uuid.UUID:
    """Ensure value is a UUID object for SQLAlchemy Uuid() columns."""
    if isinstance(val, _uuid.UUID):
        return val
    return _uuid.UUID(val)


async def search(
    db: AsyncSession,
    query: str,
    project_id: str,
    top_k: int = 8,
) -> list[dict]:
    """Semantic search over project's ingested chunks."""
    chroma_results = await query_chunks(query=query, project_id=project_id, top_k=top_k, db_session=db)

    if not chroma_results:
        return []

    chroma_ids = [r["chunk_id"] for r in chroma_results]
    chunk_stmt = select(DocumentChunk).where(DocumentChunk.chroma_id.in_(chroma_ids))
    chunk_rows = (await db.execute(chunk_stmt)).scalars().all()
    chunk_map = {c.chroma_id: c for c in chunk_rows}

    doc_ids = {c.document_id for c in chunk_rows}
    doc_map: dict = {}
    if doc_ids:
        doc_stmt = select(Document).where(Document.id.in_(list(doc_ids)))
        for d in (await db.execute(doc_stmt)).scalars().all():
            doc_map[d.id] = d

    results = []
    for r in chroma_results:
        chunk = chunk_map.get(r["chunk_id"])
        if chunk:
            doc = doc_map.get(chunk.document_id)
            results.append({
                "chunk_id": r["chunk_id"],
                "document_id": r.get("document_id", str(chunk.document_id)),
                "text": r["text"],
                "score": r["score"],
                "page_number": r.get("page_number", chunk.page_number),
                "filename": doc.filename if doc else "unknown",
                "chunk_index": chunk.chunk_index,
            })
        else:
            results.append({
                "chunk_id": r["chunk_id"],
                "document_id": r.get("document_id", ""),
                "text": r["text"],
                "score": r["score"],
                "page_number": r.get("page_number", 0),
                "filename": "unknown",
                "chunk_index": 0,
            })

    return results
