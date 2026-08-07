"""ChromaDB embedding — store and query document chunks."""

import chromadb
from core.config import settings

_client: chromadb.ClientAPI | None = None


def get_chroma_client() -> chromadb.ClientAPI:
    """Get or create ChromaDB persistent client."""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
    return _client


def get_collection() -> chromadb.Collection:
    """Get or create the knowledge_base collection."""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name="knowledge_base",
        metadata={"hnsw:space": "cosine"},
    )


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

    Returns list of dicts with 'chunk_id', 'text', 'metadata', 'score'.
    """
    collection = get_collection()

    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        where={"project_id": project_id},
    )

    output = []
    if results and results["ids"] and results["ids"][0]:
        for i, chunk_id in enumerate(results["ids"][0]):
            output.append({
                "chunk_id": chunk_id,
                "document_id": results["metadatas"][0][i].get("document_id", ""),
                "page_number": results["metadatas"][0][i].get("page_number", 0),
                "text": results["documents"][0][i],
                "score": results["distances"][0][i] if results.get("distances") else 0,
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
