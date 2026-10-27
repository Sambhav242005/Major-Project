"""Upload validation — supported knowledge-source formats, size caps, byte checks.

This registry is the single source of truth for which formats can become
project knowledge. The documents router validates uploads against it, the
signed webhook ingestion path shares the derived constants, and
`GET /documents/formats` publishes the inventory for the frontend.

Audio/video becomes available only after the operator configures the media
runtimes; ordinary document/image ingestion does not require those services.
"""

from dataclasses import dataclass
from pipelines.media import media_unavailable_reason

DOCUMENT_MAX_BYTES = 25 * 1024 * 1024  # PDF/DOCX/text — unchanged from the original cap
IMAGE_MAX_BYTES = 15 * 1024 * 1024     # images are rasterized into memory during OCR


@dataclass(frozen=True)
class UploadFormat:
    """One supported knowledge-source upload format."""

    content_type: str
    label: str
    category: str  # "document" | "image" | "audio" | "video"
    max_bytes: int
    inline_preview: bool  # safe to serve inline from GET /{id}/original


SUPPORTED_FORMATS = (
    UploadFormat("application/pdf", "PDF document", "document", DOCUMENT_MAX_BYTES, True),
    UploadFormat("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "DOCX document", "document", DOCUMENT_MAX_BYTES, False),
    UploadFormat("text/plain", "plain text file", "document", DOCUMENT_MAX_BYTES, True),
    UploadFormat("text/markdown", "Markdown file", "document", DOCUMENT_MAX_BYTES, True),
    UploadFormat("text/csv", "CSV table", "document", DOCUMENT_MAX_BYTES, True),
    UploadFormat("image/png", "PNG image", "image", IMAGE_MAX_BYTES, True),
    UploadFormat("image/jpeg", "JPEG image", "image", IMAGE_MAX_BYTES, True),
    UploadFormat("image/tiff", "TIFF image", "image", IMAGE_MAX_BYTES, True),
    UploadFormat("image/bmp", "BMP image", "image", IMAGE_MAX_BYTES, True),
    UploadFormat("image/webp", "WebP image", "image", IMAGE_MAX_BYTES, True),
)

FORMATS_BY_TYPE = {fmt.content_type: fmt for fmt in SUPPORTED_FORMATS}

# Derived flat constants; shared paths (webhook ingestion) import these names.
ALLOWED_TYPES = set(FORMATS_BY_TYPE)
MAX_FILE_SIZE = DOCUMENT_MAX_BYTES

ACCEPTED_SUMMARY = "PDF, DOCX, TXT, Markdown, CSV and images; WAV/MP3/FLAC audio and MP4/WebM video when configured"
CATEGORY_NOUN = {"document": "documents", "image": "images"}

MEDIA_FORMATS = (
    UploadFormat("audio/wav", "WAV audio", "audio", DOCUMENT_MAX_BYTES, True),
    UploadFormat("audio/x-wav", "WAV audio", "audio", DOCUMENT_MAX_BYTES, True),
    UploadFormat("audio/mpeg", "MP3 audio", "audio", DOCUMENT_MAX_BYTES, True),
    UploadFormat("audio/flac", "FLAC audio", "audio", DOCUMENT_MAX_BYTES, True),
    UploadFormat("video/mp4", "MP4 video", "video", DOCUMENT_MAX_BYTES, True),
    UploadFormat("video/webm", "WebM video", "video", DOCUMENT_MAX_BYTES, True),
)
FORMATS_BY_TYPE.update({fmt.content_type: fmt for fmt in MEDIA_FORMATS})
ALLOWED_TYPES.update(fmt.content_type for fmt in MEDIA_FORMATS)
CATEGORY_NOUN.update(audio="audio", video="video")


def available_formats() -> tuple[UploadFormat, ...]:
    return SUPPORTED_FORMATS + tuple(fmt for fmt in MEDIA_FORMATS
                                    if media_unavailable_reason(fmt.category == "video") is None)


class UploadValidationError(ValueError):
    """Validation failure carrying an end-user actionable message."""


def _sniff_mismatch(content: bytes, fmt: UploadFormat) -> bool:
    """Return True only when file bytes cannot possibly be fmt.content_type.

    Only confident magic-byte checks are applied; ambiguous payloads pass so
    exotic but valid encodings are processed, and the parser reports real
    parsing failures. text/* has no magic number — obviously binary payloads
    (NUL bytes) are rejected instead.
    """
    head = content[:16]
    if fmt.content_type in ("audio/wav", "audio/x-wav"):
        return not (head[:4] == b"RIFF" and head[8:12] == b"WAVE")
    if fmt.content_type == "audio/mpeg":
        return not (head.startswith(b"ID3") or len(head) >= 2 and head[0] == 255 and head[1] & 224 == 224)
    if fmt.content_type == "audio/flac":
        return not head.startswith(b"fLaC")
    if fmt.content_type == "video/mp4":
        return head[4:8] != b"ftyp"
    if fmt.content_type == "video/webm":
        return not head.startswith(b"\x1aE\xdf\xa3")
    if fmt.content_type == "application/pdf":
        return b"%PDF-" not in content[:1024]  # spec allows up to 1KB of leading junk
    if fmt.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return not head.startswith(b"PK\x03\x04")
    if fmt.content_type == "image/png":
        return not head.startswith(b"\x89PNG\r\n\x1a\n")
    if fmt.content_type == "image/jpeg":
        return not head.startswith(b"\xff\xd8\xff")
    if fmt.content_type == "image/tiff":
        return not (head.startswith(b"II*\x00") or head.startswith(b"MM\x00*"))
    if fmt.content_type == "image/bmp":
        return not head.startswith(b"BM")
    if fmt.content_type == "image/webp":
        return not (head[:4] == b"RIFF" and content[8:12] == b"WEBP")
    return b"\x00" in content[:8192]


def _unsupported_message(content_type: str) -> str:
    if content_type.startswith("audio/"):
        return "Unsupported audio format. Use WAV, MP3 or FLAC with configured media ingestion."
    if content_type.startswith("video/"):
        return "Unsupported video format. Use MP4 or WebM with configured media ingestion."
    return (f"File type '{content_type or 'unknown'}' is not a supported knowledge source. "
            f"Accepted knowledge sources: {ACCEPTED_SUMMARY}.")


def validate_upload(content: bytes | bytearray, filename: str | None, content_type: str | None) -> UploadFormat:
    """Validate raw upload bytes against the supported-format registry.

    Returns the matched format, or raises UploadValidationError with a
    message that tells the user what to do instead. `filename` is part of
    the signature so future extension-based hints slot in without churn.
    """
    if not content:
        raise UploadValidationError("The file is empty. Export or choose a non-empty file and try again.")
    normalized = (content_type or "").split(";", 1)[0].strip().lower()
    fmt = FORMATS_BY_TYPE.get(normalized)
    if fmt is None:
        raise UploadValidationError(_unsupported_message(normalized))
    if fmt.category in ("audio", "video"):
        reason = media_unavailable_reason(fmt.category == "video")
        if reason:
            raise UploadValidationError(reason)
    if len(content) > fmt.max_bytes:
        limit_mb = fmt.max_bytes // (1024 * 1024)
        raise UploadValidationError(
            f"The {fmt.label.lower()} exceeds the {limit_mb}MB limit for {CATEGORY_NOUN[fmt.category]}. "
            "Compress it, or split the content across documents, and upload again."
        )
    if _sniff_mismatch(bytes(content), fmt):
        raise UploadValidationError(
            f"The file content does not look like a valid {fmt.label}. It may be corrupted or renamed — "
            f"confirm the file is really a {fmt.label.lower()} and try again."
        )
    return fmt
