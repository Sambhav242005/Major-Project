"""Upload validation — spoofed, unsupported, oversized, and empty uploads (TODO 2.26 Phase 1)."""
import uuid
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from starlette.datastructures import Headers, UploadFile

from routers.documents.validation import (
    DOCUMENT_MAX_BYTES,
    IMAGE_MAX_BYTES,
    SUPPORTED_FORMATS,
    UploadValidationError,
    validate_upload,
)

# --- Unit: validate_upload accepts every registered format -----------------

REAL_DETECTION_BYTES = {
    "application/pdf": b"%PDF-1.7 artificial header bytes\n",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": b"PK\x03\x04\x14\x00\x06\x00",
    "text/plain": "résumé text with accents".encode("cp1252"),
    "text/markdown": b"# Heading\n\nBody text.\n",
    "text/csv": b"a,b\n1,2\n",
    "image/png": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01",
    "image/jpeg": b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01",
    "image/tiff": b"II*\x00\x08\x00\x00\x00\x00\x00",
    "image/bmp": b"BM\xfa\x00\x00\x00\x00\x00\x00\x00",
    "image/webp": b"RIFF\x00\x00\x00\x00WEBPVP8L",
}


def test_every_registered_format_passes_its_own_bytes():
    for fmt in SUPPORTED_FORMATS:
        matched = validate_upload(REAL_DETECTION_BYTES[fmt.content_type], "upload.bin", fmt.content_type)
        assert matched is fmt


def test_webp_detection_uses_container_fields():
    # RIFF container without the WEBP field must not pass as WebP.
    with pytest.raises(UploadValidationError):
        validate_upload(b"RIFF\x00\x00\x00\x00WAVEfmt ", "a.webp", "image/webp")


def test_task_group_and_rejection_messages_are_actionable():
    with pytest.raises(UploadValidationError) as empty:
        validate_upload(b"", "empty.txt", "text/plain")
    assert "empty" in str(empty.value).lower()
    with pytest.raises(UploadValidationError) as label:
        validate_upload(b"plain text", "a.png", "image/png")
    assert "does not look like a valid PNG image" in str(label.value)
    with pytest.raises(UploadValidationError) as binary:
        validate_upload(b"MZ\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00", "a.txt", "text/plain")
    assert "plain text file" in str(binary.value)


def test_unsupported_media_types_name_the_path_forward():
    with pytest.raises(UploadValidationError) as audio:
        validate_upload(b"ID3", "voice.mp3", "audio/mpeg")
    assert "Meetings page" in str(audio.value)
    with pytest.raises(UploadValidationError) as video:
        validate_upload(b"\x00\x00\x00 ftypisom", "clip.mp4", "video/mp4")
    assert "Video is not searchable" in str(video.value)
    with pytest.raises(UploadValidationError) as archive:
        validate_upload(b"PK\x03\x04", "bundle.zip", "application/zip")
    assert "not a supported knowledge source" in str(archive.value)


def test_per_category_size_limits():
    document = SUPPORTED_FORMATS[0]
    with pytest.raises(UploadValidationError) as oversized_image:
        validate_upload(b"a" * (IMAGE_MAX_BYTES + 1), "big.png", "image/png")
    assert f"{IMAGE_MAX_BYTES // (1024 * 1024)}MB limit for images" in str(oversized_image.value)
    with pytest.raises(UploadValidationError) as oversized_document:
        validate_upload(b"a" * (DOCUMENT_MAX_BYTES + 1), "big.pdf", document.content_type)
    assert f"{DOCUMENT_MAX_BYTES // (1024 * 1024)}MB limit for documents" in str(oversized_document.value)


# --- Router: rejected uploads never reach storage, metadata, or ingestion ---


@pytest.fixture
def upload_routes(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from core.config import settings
    from core.errors import AppError, app_error_handler
    import importlib
    routes = importlib.import_module("routers.documents.router")
    monkeypatch.setattr(settings, "CHROMA_PATH", str(tmp_path / "chroma"))
    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(routes.router, prefix="/documents")
    app.dependency_overrides[routes.get_project_id] = lambda: str(uuid.uuid4())
    app.dependency_overrides[routes.get_current_user] = lambda: MagicMock()
    app.dependency_overrides[routes.get_db] = lambda: MagicMock()
    client = TestClient(app)
    return routes, client


def _posted_file(content: bytes, filename: str, content_type: str) -> UploadFile:
    return UploadFile(BytesIO(content), filename=filename, headers=Headers({"content-type": content_type}))


def test_spoofed_image_is_rejected_before_any_persistence(upload_routes, monkeypatch):
    routes, client = upload_routes
    persisted = AsyncMock(return_value={"id": str(uuid.uuid4()), "filename": "fake.png"})
    monkeypatch.setattr(routes.doc_service, "upload_document", persisted)
    monkeypatch.setattr(routes, "write_audit_log", AsyncMock())
    started = MagicMock()
    monkeypatch.setattr(routes, "_start_ingestion", started)
    response = client.post(
        "/documents",
        files={"file": ("fake.png", b"plain text payload", "image/png")},
    )
    assert response.status_code == 400
    assert "does not look like a valid PNG image" in response.json()["detail"]
    persisted.assert_not_awaited()
    started.assert_not_called()


@pytest.mark.parametrize("content_type", ["audio/mpeg", "video/mp4", "application/zip"])
def test_unsupported_media_fails_clearly(upload_routes, monkeypatch, content_type):
    routes, client = upload_routes
    persisted = AsyncMock(return_value={"id": str(uuid.uuid4()), "filename": "x"})
    monkeypatch.setattr(routes.doc_service, "upload_document", persisted)
    started = MagicMock()
    monkeypatch.setattr(routes, "_start_ingestion", started)
    response = client.post(
        "/documents",
        files={"file": ("clip.bin", b"payload", content_type)},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "not a supported knowledge source" in detail or "not searchable" in detail
    persisted.assert_not_awaited()
    started.assert_not_called()


def test_oversized_image_reports_image_limit(upload_routes, monkeypatch):
    routes, client = upload_routes
    persisted = AsyncMock(return_value={"id": str(uuid.uuid4()), "filename": "big.png"})
    monkeypatch.setattr(routes.doc_service, "upload_document", persisted)
    started = MagicMock()
    monkeypatch.setattr(routes, "_start_ingestion", started)
    response = client.post(
        "/documents",
        files={"file": ("big.png", b"\x89PNG\r\n\x1a\n" + b"a" * IMAGE_MAX_BYTES, "image/png")},
    )
    assert response.status_code == 400
    assert "15MB limit for images" in response.json()["detail"]
    persisted.assert_not_awaited()
    started.assert_not_called()


def test_spoofed_retry_replacement_is_rejected(upload_routes, monkeypatch):
    routes, client = upload_routes
    document, project = str(uuid.uuid4()), str(uuid.uuid4())
    row = MagicMock(status="failed", file_type="text/plain")
    locked = AsyncMock(return_value=row)
    monkeypatch.setattr(routes.doc_service, "lock_document_for_mutation", locked)
    started = MagicMock()
    monkeypatch.setattr(routes, "_start_ingestion", started)
    response = client.post(
        f"/documents/{document}/retry",
        files={"file": ("replacement.png", b"plain text payload", "image/png")},
    )
    # The replacement must match the original document type first.
    assert response.status_code == 400
    assert response.json()["detail"] == "Retry file must use the original document type"
    started.assert_not_called()
    response = client.post(
        f"/documents/{document}/retry",
        files={"file": ("replacement.bin", b"MZ\x00payload", "text/plain")},
    )
    assert response.status_code == 400
    assert "plain text file" in response.json()["detail"]
    started.assert_not_called()


def test_rejected_upload_keeps_status_flow_untouched(upload_routes, monkeypatch):
    """A rejected upload creates no document, so no status can leak."""
    routes, client = upload_routes
    persisted = AsyncMock(return_value={"id": str(uuid.uuid4()), "filename": "x"})
    monkeypatch.setattr(routes.doc_service, "upload_document", persisted)
    response = client.post("/documents", files={"file": ("a.txt", b"\x00\x00", "text/plain")})
    assert response.status_code == 400
    status_probe = AsyncMock(side_effect=AssertionError("no status rows should exist"))
    monkeypatch.setattr(routes.doc_service, "get_document_status", status_probe)
    persisted.assert_not_awaited()


# --- Inventory endpoint: user-visible supported formats ---------------------


def test_formats_inventory_lists_registry_and_future_categories(upload_routes):
    from routers.documents import validation
    routes, client = upload_routes
    response = client.get("/documents/formats")
    assert response.status_code == 200
    payload = response.json()
    listed = {fmt["content_type"] for fmt in payload["formats"]}
    assert listed == set(validation.FORMATS_BY_TYPE)
    assert all(fmt["max_bytes"] == (validation.IMAGE_MAX_BYTES if fmt["category"] == "image" else validation.DOCUMENT_MAX_BYTES) for fmt in payload["formats"])
    assert {entry["category"] for entry in payload["not_yet_supported"]} == {"audio", "video"}
    assert "Meetings page" in payload["not_yet_supported"][0]["message"]


def test_formats_is_parsed_as_a_route_not_a_document(upload_routes, monkeypatch):
    """Route ordering must keep /formats ahead of the /{document_id} probe."""
    routes, client = upload_routes
    resolve = AsyncMock(return_value={"id": str(uuid.uuid4()), "filename": "x", "file_type": "text/plain", "status": "pending", "page_count": None, "error_message": None, "uploaded_at": "2026-01-01T00:00:00Z", "processed_at": None})
    monkeypatch.setattr(routes.doc_service, "get_document", resolve)
    formats = client.get("/documents/formats")
    assert formats.status_code == 200
    resolve.assert_not_awaited()
    assert client.get(f"/documents/{uuid.uuid4()}").status_code in (200, 404)
