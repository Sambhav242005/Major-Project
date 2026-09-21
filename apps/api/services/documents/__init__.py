"""Documents package — re-exports for backwards compatibility."""

from db.models import Document  # noqa: F401 — patch target compat: services.documents.Document

from .content import get_document_chunks, get_document_entities
from .crud import (
    delete_document,
    get_document,
    get_document_status,
    list_documents,
    update_document_status,
    upload_document,
)
from .stats import count_documents_by_status, get_documents_by_status

__all__ = [
    "upload_document",
    "get_document",
    "list_documents",
    "get_document_status",
    "update_document_status",
    "delete_document",
    "get_document_chunks",
    "get_document_entities",
    "get_documents_by_status",
    "count_documents_by_status",
]
