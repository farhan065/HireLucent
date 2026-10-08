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

    def __init__(self, cvs: list[dict], requirements: dict | None = None) -> None:
        self.cvs = cvs
        self.requirements = requirements or {"min_experience_years": 0, "items": []}
        self.excluded: dict[int, list[str]] = {}
        self.passed: list[int] = []
        self.matches: dict[int, list[dict]] = {}
        self.scores: dict[int, float] = {}
        self.ranks: list[int] = []
        self.results: dict[int, dict] = {}
        self.texts: dict[int, tuple[str, str]] = {}
        self.parsed: dict[int, dict] = {}
        self.failures: dict[int, str] = {}

    def load_cvs(self, job_id: int) -> list[dict]:
        return self.cvs

    def load_job(self, job_id: int) -> dict:
        return {
            "title": "Backend Engineer",
            "jd_text": "We need a backend engineer.",
            "requirements": self.requirements,
            "scoring_weights": WEIGHTS,
        }

    def save_result(self, candidate_id: int, scores: dict) -> None:
        self.results[candidate_id] = scores

    def save_exclusion(self, candidate_id: int, reasons: list[str]) -> None:
        self.excluded[candidate_id] = reasons

    def save_passed(self, candidate_id: int) -> None:
        self.passed.append(candidate_id)

    def save_matches(self, candidate_id: int, matches: list[dict], score: float) -> None:
        self.matches[candidate_id] = matches
        self.scores[candidate_id] = score

    def load_matched(self, job_id: int) -> list[dict]:
        return [
            {
                "candidate_id": candidate_id,
                "full_name": f"Candidate {candidate_id}",
                "match_score": self.scores[candidate_id],
                "matches": matches,
            }
            for candidate_id, matches in self.matches.items()
        ]

    def save_ranks(self, job_id: int, ordered_ids: list[int]) -> None:
        self.ranks = ordered_ids

    def save_cv(self, candidate_id: int, text: str, source: str, parsed: dict) -> None:
        self.texts[candidate_id] = (text, source)
        self.parsed[candidate_id] = parsed

    def save_failure(self, candidate_id: int, reason: str) -> None:
        self.failures[candidate_id] = reason


MATCHES = [{"id": "R1", "priority": "must_have", "status": "met"}]
ATS = {"score": 70.0, "keyword_coverage": 60.0, "similarity": 80.0}
DIMENSIONS = {
    name: {"score": 80, "justification": "Clear evidence in the CV."}
    for name in ("technical_skills", "experience", "qualifications")
}
WEIGHTS = {"technical_skills": 0.5, "experience": 0.3, "qualifications": 0.2}


@pytest.fixture(autouse=True)
def fake_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test calls the real AI or the vector store. Each CV gets the same
    parsed facts and the same match result."""
    monkeypatch.setattr(screening, "parse_cv", lambda text: PARSED)
    monkeypatch.setattr(screening.matching, "match", lambda cid, jid, reqs, cv: MATCHES)
    monkeypatch.setattr(screening.scoring, "ats_score", lambda reqs, jd, text: ATS)
    monkeypatch.setattr(screening.scoring, "dimension_scores", lambda *args: DIMENSIONS)


def run_graph(
    monkeypatch: pytest.MonkeyPatch, paths: list[str], requirements: dict | None = None
) -> tuple[dict, FakeStore]:
    cvs = [{"candidate_id": index, "cv_path": path} for index, path in enumerate(paths, 1)]
    store = FakeStore(cvs, requirements)
    monkeypatch.setattr(screening, "store", store)
    graph = screening.build_screening_graph(InMemorySaver())
    result = graph.invoke({"job_id": 1}, thread_config("screening-test"))
    return result["summary"], store


def test_text_is_read_from_pdf_and_docx(monkeypatch, tmp_path) -> None:
    paths = [_text_pdf(tmp_path / "a.pdf"), _docx(tmp_path / "b.docx")]

    summary, store = run_graph(monkeypatch, paths)

    assert summary == {
        "total": 2,
        "read": 2,
        "read_by_ocr": 0,
        "passed": 2,
        "excluded": 0,
        "failed": 0,
    }
    assert store.texts[1][1] == "text"
    assert "FastAPI" in store.texts[1][0]
    assert "PostgreSQL" in store.texts[2][0]
    assert store.parsed == {1: PARSED, 2: PARSED}
    assert store.failures == {}


@needs_tesseract
def test_a_scanned_pdf_is_read_by_ocr(monkeypatch, tmp_path) -> None:
    summary, store = run_graph(monkeypatch, [_scanned_pdf(tmp_path / "scan.pdf")])

    assert summary["read_by_ocr"] == 1 and summary["failed"] == 0
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

    assert (summary["total"], summary["read"], summary["failed"]) == (5, 2, 3)
    assert sorted(store.texts) == [1, 5]
    assert store.failures == {
        2: screening.FILE_DAMAGED,
        3: screening.FILE_MISSING,
        4: screening.NO_TEXT_IN_FILE,
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

    assert summary["total"] == 0


def test_a_docx_with_tables_is_read(monkeypatch, tmp_path) -> None:
    """Two-column CV templates keep their text in a table."""
    document = docx.Document()
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Skills: PostgreSQL, Docker, Redis"
    table.cell(0, 1).text = CV_TEXT
    path = tmp_path / "columns.docx"
    document.save(path)

    summary, store = run_graph(monkeypatch, [str(path)])

    assert summary["read"] == 1
    text = store.texts[1][0]
    assert "Redis" in text and "FastAPI" in text


def test_an_ocr_error_is_reported_as_such(monkeypatch, tmp_path) -> None:
    def broken_ocr(content: bytes, max_pages: int) -> str:
        raise RuntimeError("engine busy")

    monkeypatch.setattr(screening, "ocr_pdf", broken_ocr)

    summary, store = run_graph(monkeypatch, [_scanned_pdf(tmp_path / "scan.pdf")])

    assert summary["failed"] == 1
    assert store.failures[1] == screening.OCR_FAILED


@needs_tesseract
def test_scanned_cvs_are_read_side_by_side(monkeypatch, tmp_path) -> None:
    """Screening runs several branches at once; OCR must not clash."""
    paths = [_scanned_pdf(tmp_path / f"scan{index}.pdf") for index in range(3)]

    summary, store = run_graph(monkeypatch, paths)

    assert summary["read_by_ocr"] == 3 and summary["failed"] == 0


MUST_HAVE = {
    "id": "R1",
    "text": "Container orchestration",
    "category": "technical_skills",
    "priority": "must_have",
    "keywords": ["kubernetes", "k8s"],
}
ONE_MUST_HAVE = {"min_experience_years": 0, "items": [MUST_HAVE]}


def test_a_cv_parsed_before_is_not_read_or_parsed_again(monkeypatch) -> None:
    def never(*args):
        raise AssertionError("should not be called")

    monkeypatch.setattr(screening, "parse_cv", never)
    monkeypatch.setattr(screening, "extract_text", never)
    cv = {
        "candidate_id": 1,
        "cv_path": "/missing.pdf",
        "text": CV_TEXT,
        "text_source": "text",
        "parsed": PARSED,
    }
    store = FakeStore([cv])
    monkeypatch.setattr(screening, "store", store)

    graph = screening.build_screening_graph(InMemorySaver())
    summary = graph.invoke({"job_id": 1}, thread_config("screening-resume"))["summary"]

    assert summary["passed"] == 1 and summary["read"] == 0
    assert store.passed == [1]


def test_a_must_have_found_by_keyword_needs_no_ai(monkeypatch, tmp_path) -> None:
    def no_ai(*args):
        raise AssertionError("the AI should not be asked")

    monkeypatch.setattr(screening.must_haves, "generate_structured", no_ai)
    path = _text_pdf(tmp_path / "a.pdf", CV_TEXT + "\nRan services on Kubernetes.")

    summary, store = run_graph(monkeypatch, [path], ONE_MUST_HAVE)

    assert summary["passed"] == 1
    assert store.excluded == {}


def test_a_must_have_the_ai_cannot_find_excludes_the_candidate(
    monkeypatch, tmp_path
) -> None:
    answers = screening.must_haves.MustHaveAnswers(
        answers=[{"id": "R1", "shown": False}]
    )
    monkeypatch.setattr(screening.must_haves, "generate_structured", lambda p, s: answers)

    summary, store = run_graph(monkeypatch, [_text_pdf(tmp_path / "a.pdf")], ONE_MUST_HAVE)

    assert summary["excluded"] == 1
    assert store.excluded[1] == ["Missing must-have (R1): Container orchestration"]
    assert store.passed == []


def test_too_little_experience_excludes_without_asking_the_ai(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(screening, "parse_cv", lambda text: {"total_experience_years": 2})

    requirements = {"min_experience_years": 5, "items": [MUST_HAVE]}
    summary, store = run_graph(monkeypatch, [_text_pdf(tmp_path / "a.pdf")], requirements)

    assert summary["excluded"] == 1
    assert store.excluded[1] == ["2 years of experience; the job asks for at least 5 years."]


def test_the_ai_being_down_during_the_check_marks_the_cv_failed(
    monkeypatch, tmp_path
) -> None:
    def unavailable(prompt, schema):
        raise ServiceUnavailableError("AI is down")

    monkeypatch.setattr(screening.must_haves, "generate_structured", unavailable)

    summary, store = run_graph(monkeypatch, [_text_pdf(tmp_path / "a.pdf")], ONE_MUST_HAVE)

    assert summary["failed"] == 1
    assert store.failures[1] == screening.AI_UNAVAILABLE
    # The parsed facts are kept, so the next run continues from the check.
    assert 1 in store.parsed


def test_a_cv_that_met_the_must_haves_before_goes_straight_to_matching(monkeypatch) -> None:
    def never(*args):
        raise AssertionError("should not be called")

    monkeypatch.setattr(screening.must_haves, "check", never)
    cv = {
        "candidate_id": 1,
        "cv_path": "/missing.pdf",
        "text": CV_TEXT,
        "text_source": "text",
        "parsed": PARSED,
        "must_haves_met": True,
    }
    store = FakeStore([cv], ONE_MUST_HAVE)
    monkeypatch.setattr(screening, "store", store)

    graph = screening.build_screening_graph(InMemorySaver())
    graph.invoke({"job_id": 1}, thread_config("screening-match"))

    assert store.matches == {1: MATCHES}


def test_matching_failing_keeps_the_must_have_result(monkeypatch, tmp_path) -> None:
    def unavailable(*args):
        raise ServiceUnavailableError("AI is down")

    monkeypatch.setattr(screening.matching, "match", unavailable)

    summary, store = run_graph(monkeypatch, [_text_pdf(tmp_path / "a.pdf")])

    assert summary["failed"] == 1
    assert store.passed == [1]
    assert store.failures[1] == screening.AI_UNAVAILABLE


def test_matched_candidates_are_ranked_by_match_score(monkeypatch, tmp_path) -> None:
    # The branches run side by side, so the result depends on the candidate,
    # not on the order of the calls.
    statuses = {1: "partially_met", 2: "met"}
    monkeypatch.setattr(
        screening.matching,
        "match",
        lambda cid, *args: [{"id": "R1", "priority": "must_have", "status": statuses[cid]}],
    )
    paths = [_text_pdf(tmp_path / "a.pdf"), _text_pdf(tmp_path / "b.pdf")]

    summary, store = run_graph(monkeypatch, paths)

    assert store.scores == {1: 50.0, 2: 100.0}
    assert store.ranks == [2, 1]


def test_a_matched_cv_is_scored_and_saved(monkeypatch, tmp_path) -> None:
    summary, store = run_graph(monkeypatch, [_text_pdf(tmp_path / "a.pdf")])

    result = store.results[1]
    # 80 on every dimension, so the criteria score is 80 whatever the weights.
    assert result["criteria_score"] == 80.0
    # 0.8 x 80 + 0.2 x 70
    assert result["final_score"] == 78.0
    assert result["dimensions"]["experience"]["weight"] == 0.3
    assert result["ats"] == ATS


def test_a_cv_matched_before_goes_straight_to_scoring(monkeypatch) -> None:
    def never(*args):
        raise AssertionError("should not be called")

    monkeypatch.setattr(screening.matching, "match", never)
    cv = {
        "candidate_id": 1,
        "cv_path": "/missing.pdf",
        "text": CV_TEXT,
        "text_source": "text",
        "parsed": PARSED,
        "must_haves_met": True,
        "matches": MATCHES,
    }
    store = FakeStore([cv])
    monkeypatch.setattr(screening, "store", store)

    graph = screening.build_screening_graph(InMemorySaver())
    graph.invoke({"job_id": 1}, thread_config("screening-score"))

    assert store.results[1]["final_score"] == 78.0


def test_scoring_failing_keeps_the_matches(monkeypatch, tmp_path) -> None:
    def unavailable(*args):
        raise ServiceUnavailableError("AI is down")

    monkeypatch.setattr(screening.scoring, "dimension_scores", unavailable)

    summary, store = run_graph(monkeypatch, [_text_pdf(tmp_path / "a.pdf")])

    assert summary["failed"] == 1
    assert store.matches == {1: MATCHES}
    assert store.results == {}
