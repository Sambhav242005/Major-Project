"""ChromaDB collection and upsert/delete helpers."""

import chromadb

from pipelines.embeddings.client import get_chroma_client
from pipelines.embeddings.embedding_function import get_embedding_function


def get_collection() -> chromadb.Collection:
    """Get or create the knowledge_base collection with custom embeddings."""
    client = get_chroma_client()
    ef = get_embedding_function()
    kwargs: dict = {
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
    """Upsert chunk embeddings into ChromaDB."""
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


def delete_document_chunks(document_id: str) -> None:
    """Delete all chunks for a document from ChromaDB."""
    collection = get_collection()

    results = collection.get(
        where={"document_id": document_id},
    )

    if results and results["ids"]:
        collection.delete(ids=results["ids"])
