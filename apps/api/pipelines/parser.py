"""Document parsing — extract text from PDF, DOCX, and image files."""

import io
from pathlib import Path


def parse_pdf(file_content: bytes) -> list[dict]:
    """Extract text from PDF using PyMuPDF. Returns list of pages."""
    import fitz  # PyMuPDF

    doc = fitz.open(stream=file_content, filetype="pdf")
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text()
        pages.append({"text": text, "page_number": i + 1})
    doc.close()
    return pages


def parse_docx(file_content: bytes) -> list[dict]:
    """Extract text from DOCX. Returns list with single 'page'."""
    from docx import Document

    doc = Document(io.BytesIO(file_content))
    text = "\n\n".join(para.text for para in doc.paragraphs if para.text.strip())
    return [{"text": text, "page_number": 1}]


def parse_image(file_content: bytes, filename: str) -> list[dict]:
    """Extract text from image using Tesseract OCR."""
    import pytesseract
    from PIL import Image

    img = Image.open(io.BytesIO(file_content))
    text = pytesseract.image_to_string(img)
    return [{"text": text, "page_number": 1}]


def parse_txt(file_content: bytes) -> list[dict]:
    """Parse plain text file."""
    text = file_content.decode("utf-8", errors="replace")
    return [{"text": text, "page_number": 1}]


def has_text_layer(pdf_content: bytes) -> bool:
    """Check if PDF has a text layer (avoids unnecessary OCR)."""
    import fitz

    doc = fitz.open(stream=pdf_content, filetype="pdf")
    for page in doc:
        if page.get_text().strip():
            doc.close()
            return True
    doc.close()
    return False


def parse_document(file_content: bytes, filename: str, file_type: str) -> list[dict]:
    """Route to correct parser based on file type.

    Returns list of pages, each with 'text' and 'page_number'.
    """
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        if has_text_layer(file_content):
            return parse_pdf(file_content)
        else:
            return parse_image(file_content, filename)
    elif ext == ".docx":
        return parse_docx(file_content)
    elif ext in (".txt", ".md", ".csv"):
        return parse_txt(file_content)
    elif ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"):
        return parse_image(file_content, filename)
    else:
        # Try text parsing as fallback
        return parse_txt(file_content)
