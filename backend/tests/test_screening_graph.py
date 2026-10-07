"""Tests for the CV Screening graph. Files are made on the spot, and the
database is replaced with a stand-in that records what would be saved."""

import shutil
from pathlib import Path

import docx
import pymupdf
import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.core.errors import ServiceUnavailableError
from app.graphs.base import thread_config
from app.graphs.screening import graph as screening

CV_TEXT = (
    "Sample Person\n"
    "Backend Engineer with five years of Python and FastAPI experience.\n"
    "Skills: PostgreSQL, Docker, REST APIs and automated testing.\n"
    "Education: BSc in Computer Science."
)
PARSED = {"skills": ["Python", "FastAPI"], "total_experience_years": 5}
needs_tesseract = pytest.mark.skipif(
    shutil.which("tesseract") is None, reason="Tesseract is not installed here"
)


def _text_pdf(path: Path, text: str = CV_TEXT) -> str:
    pdf = pymupdf.open()
    pdf.new_page().insert_textbox(pymupdf.Rect(50, 50, 550, 400), text, fontsize=14)
    pdf.save(path)
    return str(path)


def _scanned_pdf(path: Path, text: str = CV_TEXT) -> str:
    """A PDF that holds only a picture of the text, like a scan."""
    source = pymupdf.open()
    page = source.new_page()
    page.insert_textbox(pymupdf.Rect(50, 50, 550, 400), text, fontsize=14)
    scan = pymupdf.open()
    scan_page = scan.new_page()
    scan_page.insert_image(scan_page.rect, pixmap=page.get_pixmap(dpi=200))
    scan.save(path)
    return str(path)


def _docx(path: Path, text: str = CV_TEXT) -> str:
    document = docx.Document()
    for line in text.splitlines():
        document.add_paragraph(line)
    document.save(path)
    return str(path)


class FakeStore:
    """Stands in for the database."""

    def __init__(self, cvs: list[dict]) -> None:
        self.cvs = cvs
        self.texts: dict[int, tuple[str, str]] = {}
        self.parsed: dict[int, dict] = {}
        self.failures: dict[int, str] = {}

    def load_cvs(self, job_id: int) -> list[dict]:
        return self.cvs

    def save_cv(self, candidate_id: int, text: str, source: str, parsed: dict) -> None:
        self.texts[candidate_id] = (text, source)
        self.parsed[candidate_id] = parsed

    def save_failure(self, candidate_id: int, reason: str) -> None:
        self.failures[candidate_id] = reason


@pytest.fixture(autouse=True)
def fake_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test calls the real AI. Each CV gets the same parsed facts."""
    monkeypatch.setattr(screening, "parse_cv", lambda text: PARSED)


def run_graph(monkeypatch: pytest.MonkeyPatch, paths: list[str]) -> tuple[dict, FakeStore]:
    cvs = [{"candidate_id": index, "cv_path": path} for index, path in enumerate(paths, 1)]
    store = FakeStore(cvs)
    monkeypatch.setattr(screening, "store", store)
    graph = screening.build_screening_graph(InMemorySaver())
    result = graph.invoke({"job_id": 1}, thread_config("screening-test"))
    return result["summary"], store


def test_text_is_read_from_pdf_and_docx(monkeypatch, tmp_path) -> None:
    paths = [_text_pdf(tmp_path / "a.pdf"), _docx(tmp_path / "b.docx")]

    summary, store = run_graph(monkeypatch, paths)

    assert summary == {"total": 2, "read": 2, "read_by_ocr": 0, "failed": 0}
    assert store.texts[1][1] == "text"
    assert "FastAPI" in store.texts[1][0]
    assert "PostgreSQL" in store.texts[2][0]
    assert store.parsed == {1: PARSED, 2: PARSED}
    assert store.failures == {}


@needs_tesseract
def test_a_scanned_pdf_is_read_by_ocr(monkeypatch, tmp_path) -> None:
    summary, store = run_graph(monkeypatch, [_scanned_pdf(tmp_path / "scan.pdf")])

    assert summary == {"total": 1, "read": 0, "read_by_ocr": 1, "failed": 0}
    text, source = store.texts[1]
    assert source == "ocr"
    assert "Python" in text


def test_a_scan_that_ocr_cannot_read_is_marked_failed(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(screening, "ocr_pdf", lambda content, max_pages: "")

    summary, store = run_graph(monkeypatch, [_text_pdf(tmp_path / "empty.pdf", "Hi")])

    assert summary["failed"] == 1
    assert store.failures[1] == screening.NO_TEXT
    assert store.texts == {}


def test_a_cv_is_marked_failed_when_the_ai_is_not_available(
    monkeypatch, tmp_path
) -> None:
    def unavailable(text: str) -> dict:
        raise ServiceUnavailableError("AI is down")

    monkeypatch.setattr(screening, "parse_cv", unavailable)

    summary, store = run_graph(monkeypatch, [_text_pdf(tmp_path / "a.pdf")])

    assert summary["failed"] == 1
    assert store.failures[1] == screening.AI_UNAVAILABLE
    assert store.parsed == {}


def test_one_bad_cv_does_not_stop_the_others(monkeypatch, tmp_path) -> None:
    damaged = tmp_path / "damaged.pdf"
    damaged.write_bytes(b"%PDF-1.7 this is not a real PDF")
    paths = [
        _text_pdf(tmp_path / "good.pdf"),
        str(damaged),
        str(tmp_path / "missing.pdf"),
        _docx(tmp_path / "short.docx", "Hi"),
        _docx(tmp_path / "good.docx"),
    ]

    summary, store = run_graph(monkeypatch, paths)

    assert summary == {"total": 5, "read": 2, "read_by_ocr": 0, "failed": 3}
    assert sorted(store.texts) == [1, 5]
    assert store.failures == {
        2: screening.FILE_DAMAGED,
        3: screening.FILE_MISSING,
        4: screening.NO_TEXT,
    }


def test_an_unexpected_problem_is_recorded_against_that_cv_only(
    monkeypatch, tmp_path
) -> None:
    def broken_save_cv(candidate_id: int, text: str, source: str, parsed: dict) -> None:
        raise RuntimeError("database unavailable")

    cvs = [{"candidate_id": 1, "cv_path": _text_pdf(tmp_path / "a.pdf")}]
    store = FakeStore(cvs)
    store.save_cv = broken_save_cv
    monkeypatch.setattr(screening, "store", store)
    graph = screening.build_screening_graph(InMemorySaver())

    result = graph.invoke({"job_id": 1}, thread_config("screening-test-2"))

    assert result["summary"]["failed"] == 1
    assert store.failures[1] == screening.UNEXPECTED


def test_no_cvs_gives_an_empty_summary(monkeypatch) -> None:
    summary, store = run_graph(monkeypatch, [])

    assert summary == {"total": 0, "read": 0, "read_by_ocr": 0, "failed": 0}
