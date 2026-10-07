"""Reads the text out of uploaded files (PDF, DOCX, TXT and Markdown)."""

import io
from pathlib import PurePath

import docx
import pymupdf

from app.core.errors import AppError

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
# The first bytes of real PDF and DOCX files. A file that claims one of
# these types but does not start this way is rejected.
SIGNATURES = {".pdf": b"%PDF", ".docx": b"PK"}


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
    with pymupdf.open(stream=content, filetype="pdf") as pdf:
        pages = []
        for page in list(pdf)[:max_pages]:
            recognised = page.get_textpage_ocr(language="eng", dpi=300, full=True)
            pages.append(page.get_text(textpage=recognised).strip())
    return "\n\n".join(page for page in pages if page).strip()


def extract_text(extension: str, content: bytes) -> str:
    """Return the text of a file. An empty string means no text was found,
    for example in a scanned PDF."""
    if extension == ".pdf":
        with pymupdf.open(stream=content, filetype="pdf") as pdf:
            return "\n\n".join(page.get_text().strip() for page in pdf).strip()
    if extension == ".docx":
        document = docx.Document(io.BytesIO(content))
        return "\n\n".join(
            paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()
        )
    return content.decode("utf-8", errors="replace").strip()
