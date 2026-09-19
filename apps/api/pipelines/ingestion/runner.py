"""Ingestion runner — session management and background entry point."""

from pipelines.ingestion.pipeline import _ingest_document_body


async def ingest_document(session_factory, document_id: str, file_content: bytes) -> None:
    """Run the full ingestion pipeline for a document.

    Opens its own DB session so the work survives after the request's
    dependency session is closed — Starlette runs background tasks after
    dependency teardown.
    """
    async with session_factory() as db:
        await _ingest_document_body(db, document_id, file_content)
