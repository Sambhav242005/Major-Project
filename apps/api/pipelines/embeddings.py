"""ChromaDB embedding — store and query document chunks with custom embeddings."""

import chromadb
from core.config import settings

_client: chromadb.ClientAPI | None = None


class OllamaEmbeddingFunction(chromadb.EmbeddingFunction):
    """Custom embedding function that calls Ollama for embeddings."""

    def __call__(self, input: chromadb.Documents) -> chromadb.Embeddings:
        import httpx

        model = settings.OLLAMA_EMBEDDING_MODEL
        url = f"{settings.OLLAMA_BASE_URL}/api/embed"

        with httpx.Client(timeout=60) as client:
            resp = client.post(url, json={"model": model, "input": input})
            resp.raise_for_status()
            data = resp.json()
            return data["embeddings"]


def get_chroma_client() -> chromadb.ClientAPI:
    """Get or create ChromaDB persistent client."""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
    return _client


_embedding_fn = None


def get_embedding_function():
    global _embedding_fn
    if _embedding_fn is None:
        try:
            _embedding_fn = OllamaEmbeddingFunction()
        except Exception:
            _embedding_fn = None
    return _embedding_fn


def get_collection() -> chromadb.Collection:
    """Get or create the knowledge_base collection with custom embeddings."""
    client = get_chroma_client()
    ef = get_embedding_function()
    kwargs = {
        "name": "knowledge_base",
        "metadata": {"hnsw:space": "cosine"},
    }
    if ef is not None:
        kwargs["embedding_function"] = ef
    return client.get_or_create_collection(**kwargs)


def upsert_chunks(
    chunks: list[dict],
    project_id: str,
    document_id: str,
) -> list[str]:
    """Upsert chunk embeddings into ChromaDB.

    Args:
        chunks: List of dicts with 'text', 'chunk_index', 'page_number'
        project_id: Project UUID string
        document_id: Document UUID string

    Returns:
        List of Chroma IDs assigned to each chunk.
    """
    collection = get_collection()

    ids = []
    documents = []
    metadatas = []

    for chunk in chunks:
        chroma_id = f"{document_id}_chunk_{chunk['chunk_index']}"
        ids.append(chroma_id)
        documents.append(chunk["text"])
        metadatas.append({
            "project_id": project_id,
            "document_id": document_id,
            "chunk_index": chunk["chunk_index"],
            "page_number": chunk.get("page_number") or 0,
        })

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )

    return ids


def query_chunks(
    query: str,
    project_id: str,
    top_k: int = 8,
) -> list[dict]:
    """Query ChromaDB for similar chunks within a project.

    Returns list of dicts with 'chunk_id', 'text', 'metadata', 'score', 'filename'.
    """
    collection = get_collection()

    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        where={"project_id": project_id},
    )

    # Build a doc_id -> filename map via DB
    doc_filename_map = {}
    try:
        import uuid as _uuid
        from db.session import async_session_factory
        from sqlalchemy import select
        from db.models import Document

        doc_ids = set()
        if results and results["metadatas"] and results["metadatas"][0]:
            for meta in results["metadatas"][0]:
                did = meta.get("document_id")
                if did:
                    doc_ids.add(did)

        if doc_ids:
            import asyncio
            async def _fetch():
                async with async_session_factory() as session:
                    stmt = select(Document.id, Document.filename).where(
                        Document.id.in_([_uuid.UUID(d) for d in doc_ids])
                    )
                    res = await session.execute(stmt)
                    return {str(r.id): r.filename for r in res.all()}

            if asyncio.get_event_loop().is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    doc_filename_map = pool.submit(asyncio.run, _fetch()).result()
            else:
                doc_filename_map = asyncio.run(_fetch())
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


def delete_document_chunks(document_id: str) -> None:
    """Delete all chunks for a document from ChromaDB."""
    collection = get_collection()

    # Find all chunks for this document
    results = collection.get(
        where={"document_id": document_id},
    )

    if results and results["ids"]:
        collection.delete(ids=results["ids"])
