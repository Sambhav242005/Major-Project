"""ChromaDB similarity query."""

import asyncio
from functools import partial

from pipelines.embeddings.embedding_function import (
    TASK_QUERY,
    get_embedding_function,
)
from pipelines.embeddings.store import get_collection


def _embed_and_query(
    collection,
    query: str,
    project_id: str,
    top_k: int,
) -> dict | None:
    """Embed the query as a RETRIEVAL_QUERY, then search. Runs in an executor."""
    query_embeddings = get_embedding_function(TASK_QUERY)([query])
    return collection.query(
        query_embeddings=query_embeddings,
        n_results=top_k,
        where={"project_id": project_id},
    )


async def query_chunks(
    query: str,
    project_id: str,
    top_k: int = 8,
    db_session=None,
) -> list[dict]:
    """Query ChromaDB for similar chunks within a project."""
    collection = get_collection()

    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        None,
        partial(
            _embed_and_query,
            collection,
            query,
            project_id,
            top_k,
        ),
    )

    doc_filename_map: dict[str, str] = {}
    try:
        if db_session:
            import uuid as _uuid
            from sqlalchemy import select as sa_select
            from db.models import Document

            doc_ids = set()
            if results and results["metadatas"] and results["metadatas"][0]:
                for meta in results["metadatas"][0]:
                    did = meta.get("document_id")
                    if did:
                        doc_ids.add(did)

            if doc_ids:
                stmt = sa_select(Document.id, Document.filename).where(
                    Document.id.in_([_uuid.UUID(d) for d in doc_ids])
                )
                res = await db_session.execute(stmt)
                doc_filename_map = {str(r.id): r.filename for r in res.all()}
    except Exception:
        pass

    output = []
    if results and results["ids"] and results["ids"][0]:
        for i, chunk_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            doc_id = meta.get("document_id", "")
            output.append({
                "chunk_id": chunk_id,
                "document_id": doc_id,
                "page_number": meta.get("page_number", 0),
                "text": results["documents"][0][i],
                "score": results["distances"][0][i] if results.get("distances") else 0,
                "filename": doc_filename_map.get(doc_id, "unknown"),
            })

    return output
