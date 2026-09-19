"""Ingestion package — re-exports original public API."""

from pipelines.ingestion.notifier import _notify, _notify_doc, set_doc_notifier
from pipelines.ingestion.pipeline import _ingest_document_body, _offload
from pipelines.ingestion.runner import ingest_document

__all__ = [
    "_notify_doc",
    "set_doc_notifier",
    "_notify",
    "_offload",
    "_ingest_document_body",
    "ingest_document",
]
