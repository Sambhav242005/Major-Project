"""Shim for backward compatibility — re-exports from routers.documents package."""

try:
    from routers.documents import router  # noqa: F401
    from routers.documents.validation import ALLOWED_TYPES, MAX_FILE_SIZE  # noqa: F401
    from routers.documents.ingestion_tasks import (  # noqa: F401
        _doc_subscribers,
        _running_ingestions,
        _notify_doc_subscribers,
        _start_ingestion,
    )
except Exception:  # pragma: no cover
    pass

__all__ = [
    "router",
    "ALLOWED_TYPES",
    "MAX_FILE_SIZE",
    "_doc_subscribers",
    "_running_ingestions",
    "_notify_doc_subscribers",
    "_start_ingestion",
]
