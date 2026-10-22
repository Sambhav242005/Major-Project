"""Private durable originals, stored alongside the persistent vector directory."""
from pathlib import Path
import os
import uuid

from core.config import settings


def original_path(project_id: str, document_id: str) -> Path:
    # UUID-only path segments prevent filenames or metadata from escaping storage.
    return Path(settings.CHROMA_PATH).resolve().parent / "document_originals" / str(uuid.UUID(project_id)) / str(uuid.UUID(document_id))


def save_original(project_id: str, document_id: str, content: bytes) -> None:
    path = original_path(project_id, document_id)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}")
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as target:
            target.write(content)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_original(project_id: str, document_id: str) -> bytes:
    return original_path(project_id, document_id).read_bytes()


def delete_original(project_id: str, document_id: str) -> None:
    original_path(project_id, document_id).unlink(missing_ok=True)
