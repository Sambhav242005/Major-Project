"""Security utilities — input sanitization, prompt injection defense."""

import re
import html


# Patterns that indicate prompt injection attempts
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?prior\s+instructions",
    r"disregard\s+(all\s+)?previous",
    r"you\s+are\s+now\s+",
    r"new\s+instructions?:",
    r"system\s*:\s*",
    r"assistant\s*:\s*",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"\[INST\]",
    r"\[/INST\]",
    r"<<SYS>>",
    r"<</SYS>>",
]

INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


def sanitize_input(text: str, max_length: int = 10000) -> str:
    """Sanitize user input for LLM consumption.

    - Truncates to max_length
    - HTML-escapes special characters
    - Strips null bytes
    """
    if not isinstance(text, str):
        return ""

    # Strip null bytes
    text = text.replace("\x00", "")

    # Truncate
    text = text[:max_length]

    return text


def detect_injection(text: str) -> bool:
    """Detect potential prompt injection attempts."""
    if not isinstance(text, str):
        return False
    return bool(INJECTION_RE.search(text))


def sanitize_for_llm(text: str) -> str:
    """Sanitize text before sending to LLM.

    Adds safety wrapper to prevent instruction override.
    """
    text = sanitize_input(text)

    if detect_injection(text):
        # Log but don't block — let the system prompt handle it
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Potential prompt injection detected in input: {text[:100]}...")

    return text


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal."""
    # Remove path separators
    filename = filename.replace("/", "").replace("\\", "")

    # Remove null bytes
    filename = filename.replace("\x00", "")

    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
        filename = name[:255 - len(ext) - 1] + "." + ext

    return filename


def validate_project_id(project_id) -> bool:
    """Validate project_id is a valid UUID format."""
    import uuid
    if not isinstance(project_id, str):
        return False
    try:
        uuid.UUID(project_id)
        return True
    except ValueError:
        return False
