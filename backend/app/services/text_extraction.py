"""Reads the text out of uploaded files (PDF, DOCX, TXT and Markdown)."""

import io
import threading
from pathlib import PurePath

import docx
import pymupdf
from docx.oxml.ns import qn

from app.core.errors import AppError

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
# The first bytes of real PDF and DOCX files. A file that claims one of
# these types but does not start this way is rejected.
SIGNATURES = {".pdf": b"%PDF", ".docx": b"PK"}

# PyMuPDF, and the OCR engine under it, cannot be used from two threads at
# once. Screening reads several CVs side by side, so every use of it goes
# through this lock. Only the file reading waits; the AI calls stay parallel.
_PDF_LOCK = threading.Lock()

_PARAGRAPH = qn("w:p")
_TEXT = qn("w:t")
# Word stores a text box twice: the modern version and an older fallback.
_FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"


class UnsupportedFileError(AppError):
    status_code = 415
    code = "unsupported_file"


class FileTooLargeError(AppError):
    status_code = 413
    code = "file_too_large"


def check_file(filename: str, content: bytes, max_mb: int) -> str:
    """Check the type and size of an upload. Returns the file extension."""
    extension = PurePath(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileError("Upload a PDF, DOCX, TXT or Markdown file.")
    if len(content) > max_mb * 1024 * 1024:
        raise FileTooLargeError(f"The file is larger than {max_mb} MB.")
    if not content:
        raise UnsupportedFileError("The file is empty.")
    signature = SIGNATURES.get(extension)
    if signature and not content.startswith(signature):
        raise UnsupportedFileError(
            "The file's content does not match its type. Check the file and try again."
        )
    return extension


def ocr_pdf(content: bytes, max_pages: int) -> str:
    """Read a scanned PDF by recognising the text in its page images.

    Uses Tesseract through PyMuPDF. Only the first pages are read, which
    keeps a very long scan from holding up the rest of a batch.
    """
    with _PDF_LOCK, pymupdf.open(stream=content, filetype="pdf") as pdf:
        pages = []
        for page in list(pdf)[:max_pages]:
            recognised = page.get_textpage_ocr(language="eng", dpi=300, full=True)
            pages.append(page.get_text(textpage=recognised).strip())
    return "\n\n".join(page for page in pages if page).strip()


def extract_text(extension: str, content: bytes) -> str:
    """Return the text of a file. An empty string means no text was found,
    for example in a scanned PDF."""
    if extension == ".pdf":
        with _PDF_LOCK, pymupdf.open(stream=content, filetype="pdf") as pdf:
            return "\n\n".join(page.get_text().strip() for page in pdf).strip()
    if extension == ".docx":
        return _docx_text(content)
    return content.decode("utf-8", errors="replace").strip()


def _docx_text(content: bytes) -> str:
    """All text of a Word file, in reading order, including tables and text
    boxes, where many CV templates put their columns."""
    body = docx.Document(io.BytesIO(content)).element.body
    paragraphs: dict[object, list[str]] = {}
    for node in body.iter(_TEXT):
        if any(ancestor.tag == _FALLBACK for ancestor in node.iterancestors()):
            continue
        # Text in a text box belongs to the box's own paragraph, not to the
        # paragraph the box is anchored in.
        paragraph = next(node.iterancestors(_PARAGRAPH), None)
        paragraphs.setdefault(paragraph, []).append(node.text or "")
    lines = ("".join(parts).strip() for parts in paragraphs.values())
    return "\n\n".join(line for line in lines if line)
