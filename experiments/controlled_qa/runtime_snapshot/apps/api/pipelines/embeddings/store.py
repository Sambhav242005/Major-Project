"""ChromaDB collection and upsert/delete helpers."""

import logging

import chromadb

from core.config import settings
from core.errors import AppError
from pipelines.embeddings.client import get_chroma_client
from pipelines.embeddings.embedding_function import (
    TASK_DOCUMENT,
    get_embedding_function,
)

logger = logging.getLogger(__name__)

COLLECTION_NAME = "knowledge_base"

# Records which model produced the vectors in this collection. Embedding spaces
# from different providers/models are not comparable, so a mismatch must fail
# loudly instead of returning irrelevant chunks.
FINGERPRINT_KEY = "embedding_fingerprint"

# Chroma-managed keys that must not be echoed back in Collection.modify().
_CHROMA_RESERVED_KEYS = frozenset({
    "hnsw:space", "hnsw:M", "hnsw:ef_construction", "hnsw:ef_search",
    "hnsw:ml", "spann:space",
})

_MISMATCH_HELP = (
    "Embedding spaces from different providers/models cannot be compared. "
    "Re-embed the existing knowledge base before switching, e.g.: stop the API, "
    "delete the contents of CHROMA_PATH (e.g. ./chroma_data), then re-upload each "
    "document (or POST /documents/{id}/retry) so chunks are embedded with the new "
    "model."
)


class EmbeddingSpaceMismatchError(AppError):
    """The configured embedding model does not match the collection's vectors.

    A 409 rather than a 500: the configuration is internally consistent, it
    just conflicts with the stored vector space. The detail carries the
    remediation steps, which ``app_error_handler`` and ``generator_sse_stream``
    both forward to the client.
    """

    status_code = 409
    detail = "Embedding space mismatch"
    error_code = "embedding_space_mismatch"


def embedding_fingerprint() -> str:
    """Identity of the vector space currently configured."""
    dim = settings.EMBEDDING_OUTPUT_DIM or "default"
    return f"{settings.EMBEDDING_PROVIDER}:{settings.EMBEDDING_MODEL}:{dim}"


def _stamp_fingerprint(collection: chromadb.Collection, fingerprint: str) -> None:
    preserved = {
        key: value
        for key, value in (collection.metadata or {}).items()
        if key not in _CHROMA_RESERVED_KEYS
    }
    collection.modify(metadata={**preserved, FINGERPRINT_KEY: fingerprint})
    logger.info("Stamped Chroma collection %s with %s", COLLECTION_NAME, fingerprint)


def _verify_embedding_space(collection: chromadb.Collection, fingerprint: str) -> None:
    existing = (collection.metadata or {}).get(FINGERPRINT_KEY)

    if existing == fingerprint:
        return

    if existing is None:
        # Collection predates fingerprints, so its vectors have unknown
        # provenance. Adopt it for the default provider (no behaviour change for
        # existing deployments) but refuse a provider switch, which would mix
        # vector spaces.
        count = collection.count()
        if count > 0 and settings.EMBEDDING_PROVIDER != "openai":
            raise EmbeddingSpaceMismatchError(
                f"Chroma collection {COLLECTION_NAME!r} holds "
                f"{count} vectors from an unrecorded embedding model, "
                f"but EMBEDDING_PROVIDER is {settings.EMBEDDING_PROVIDER!r} "
                f"({settings.EMBEDDING_MODEL}). {_MISMATCH_HELP}"
            )
        if count > 0:
            # We cannot recover the model that wrote these vectors, so this
            # stamp is an assumption, not a verification. It is the right call
            # (a mismatch here would break every existing deployment), but it
            # means a model change shipped in the same deploy as this upgrade
            # would go undetected. Documented in docs/TODO.md §2.22.
            logger.warning(
                "Chroma collection %r holds %d pre-fingerprint vectors; "
                "assuming they were built with the current embedding config (%s). "
                "Vector provenance is unverified for this collection.",
                COLLECTION_NAME, count, fingerprint,
            )
        _stamp_fingerprint(collection, fingerprint)
        return

    raise EmbeddingSpaceMismatchError(
        f"Chroma collection {COLLECTION_NAME!r} was built with {existing!r} but the "
        f"current configuration produces {fingerprint!r}. {_MISMATCH_HELP}"
    )


def get_collection() -> chromadb.Collection:
    """Get or create the knowledge_base collection and verify its vector space.

    No ``embedding_function`` is registered with Chroma on purpose: every write
    and every query passes vectors explicitly, which is what lets ingestion use
    Gemini's ``RETRIEVAL_DOCUMENT`` task type and search use
    ``RETRIEVAL_QUERY`` from the same collection.
    """
    client = get_chroma_client()
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    _verify_embedding_space(collection, embedding_fingerprint())
    return collection


def upsert_chunks(
    chunks: list[dict],
    project_id: str,
    document_id: str,
) -> list[str]:
    """Upsert chunk embeddings into ChromaDB."""
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

    if not ids:
        return []

    collection = get_collection()

    # Embed explicitly so the document taskType is applied and so the collection
    # holds vectors from exactly one model.
    embeddings = get_embedding_function(TASK_DOCUMENT)(documents)

    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embeddings,
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
