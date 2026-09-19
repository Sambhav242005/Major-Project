"""SSE notifier callback for ingestion progress."""

# SSE notification callback (set by documents router)
_notify_doc = None


def set_doc_notifier(notifier):
    global _notify_doc
    _notify_doc = notifier


def _notify(document_id: str, event: dict):
    if _notify_doc:
        _notify_doc(document_id, event)
