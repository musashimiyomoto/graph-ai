"""Text extraction for uploaded documents (Vector Collections upload)."""

from io import BytesIO
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from exceptions import UnsupportedDocumentTypeError


def extract_text(filename: str, content: bytes) -> str:
    """Extract plain text from an uploaded document's raw bytes.

    Args:
        filename: The uploaded file's original name, used only for its
            extension.
        content: The file's raw bytes.

    Returns:
        The extracted text.

    Raises:
        UnsupportedDocumentTypeError: If the file is a `.pdf`/`.docx` that
            can't be parsed, or any other type that isn't valid UTF-8 text.

    """
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(content)
    if suffix == ".docx":
        return _extract_docx(content)
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        message = f"Unsupported document type: '{suffix or filename}'"
        raise UnsupportedDocumentTypeError(message=message) from exc


def _extract_pdf(content: bytes) -> str:
    """Extract text from PDF bytes."""
    try:
        reader = PdfReader(BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        message = "Could not parse PDF document"
        raise UnsupportedDocumentTypeError(message=message) from exc


def _extract_docx(content: bytes) -> str:
    """Extract text from DOCX bytes."""
    try:
        document = Document(BytesIO(content))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    except Exception as exc:
        message = "Could not parse DOCX document"
        raise UnsupportedDocumentTypeError(message=message) from exc
