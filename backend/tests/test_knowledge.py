"""Tests for the Knowledge Base: file checks, text extraction and chunking."""

import io

import docx
import pymupdf
import pytest

from app.rag.chunking import chunk_text, split_questions
from app.services.text_extraction import (
    FileTooLargeError,
    UnsupportedFileError,
    check_file,
    extract_text,
)


def _pdf(text: str) -> bytes:
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((72, 72), text)
        return pdf.tobytes()


def _docx(paragraphs: list[str]) -> bytes:
    document = docx.Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_text_is_read_from_a_pdf() -> None:
    assert "Backend Engineer" in extract_text(".pdf", _pdf("Backend Engineer"))


def test_text_is_read_from_a_docx() -> None:
    text = extract_text(".docx", _docx(["About the role", "Build APIs."]))

    assert text == "About the role\n\nBuild APIs."


def test_plain_text_is_read_as_it_is() -> None:
    assert extract_text(".txt", b"  Hello  ") == "Hello"


def test_unsupported_file_type_is_rejected() -> None:
    with pytest.raises(UnsupportedFileError):
        check_file("notes.exe", b"data", max_mb=10)


def test_file_that_is_not_what_its_name_says_is_rejected() -> None:
    with pytest.raises(UnsupportedFileError):
        check_file("template.pdf", b"this is not a pdf", max_mb=10)


def test_file_over_the_size_limit_is_rejected() -> None:
    with pytest.raises(FileTooLargeError):
        check_file("big.txt", b"x" * (2 * 1024 * 1024), max_mb=1)


def test_valid_file_returns_its_extension() -> None:
    assert check_file("Template.PDF", _pdf("text"), max_mb=10) == ".pdf"


def test_short_text_stays_in_one_chunk() -> None:
    assert chunk_text("One paragraph.\n\nAnother.") == ["One paragraph.\n\nAnother."]


def test_long_text_is_split_with_overlap() -> None:
    paragraphs = [f"Paragraph {number} " + "word " * 60 for number in range(8)]

    chunks = chunk_text("\n\n".join(paragraphs), max_chars=700, overlap=80)

    assert len(chunks) > 1
    assert all(len(chunk) <= 700 + 80 + 2 for chunk in chunks)
    # The start of each later chunk repeats the end of the one before.
    assert chunks[1][:80] == chunks[0][-80:]


def test_one_huge_paragraph_is_cut_to_size() -> None:
    chunks = chunk_text("x" * 3000, max_chars=1000, overlap=100)

    assert all(len(chunk) <= 1000 for chunk in chunks)
    assert len(chunks) >= 3


def test_questions_are_split_one_per_line() -> None:
    text = "1. How do you design a REST API?\n- Explain database indexing.\n\nok"

    assert split_questions(text) == [
        "How do you design a REST API?",
        "Explain database indexing.",
    ]
