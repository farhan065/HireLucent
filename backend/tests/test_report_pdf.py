"""Tests for the assessment report PDF: what it shows, that every value is
escaped, the interviewer's time zone, the file name and the endpoint."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.core.errors import ConflictError
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import create_app
from app.models import Assessment
from app.models.enums import UserRole
from app.services import evaluation_service, report_pdf
from tests.test_final_assessment import COVERAGE, PAIRS, findings

START = datetime(2026, 10, 13, 8, 0, tzinfo=timezone.utc)


def _context(**changes) -> dict:
    context = {
        "candidate_name": "Rakib Hossain",
        "job_title": "Backend Engineer",
        "job_code": "HL-BE-01",
        "interview_when": "Mon 13 Oct 2026, 2:00 – 2:47 PM",
        "status": "approved",
        "approved_by": "Demo Interviewer",
        "approved_on": "Sun 18 Oct 2026",
        "cv_score": 83.0,
        "interview_score": 75.7,
        "overall_score": 78.6,
        "suitability": "strong_fit",
        "answers_evaluated": 4,
        "summary": "A strong fit for the role.",
        "strengths": [
            {
                "id": "S1",
                "text": "Explains FastAPI dependencies clearly.",
                "sources": [findings.transcript_source(PAIRS[1])],
            }
        ],
        "weaknesses": [],
        "gaps": findings.evidence_gaps(COVERAGE),
        "areas_to_verify": findings.areas_to_verify(PAIRS, COVERAGE),
        "coverage": COVERAGE,
        "pairs": PAIRS,
        "generated_on": "Sun 18 Oct 2026, 6:50 PM",
    }
    return {**context, **changes}


def _text(content: bytes) -> list[str]:
    document = pymupdf.open(stream=content, filetype="pdf")
    # Read as PDF viewers do, with "fi" and similar ligatures as plain letters.
    return [page.get_text(flags=pymupdf.TEXT_PRESERVE_WHITESPACE) for page in document]


def test_the_report_comes_first_and_the_appendix_after() -> None:
    pages = _text(report_pdf.build_pdf(_context()))

    first, rest = pages[0], " ".join(pages[1:])
    assert "Rakib Hossain" in first and "A strong fit for the role." in first
    assert "78.6" in first and "Strong fit" in first and "Approved" in first
    assert "runs a function" in first and "Evidence gaps" in first
    assert "A · Requirement coverage" in rest and "B · Questions and scores" in rest
    assert "Not explored" in rest and "Not answered" in rest and "Small talk" in rest
    assert f"Page 1 of {len(pages)}" in first
    assert "Confidential: for the hiring team only" in pages[-1]


def test_a_draft_says_so() -> None:
    first = _text(report_pdf.build_pdf(_context(status="draft", approved_by=None)))[0]

    assert "Draft" in first and "not yet reviewed" in first


def test_without_an_overall_score_the_reason_is_shown() -> None:
    context = _context(interview_score=None, overall_score=None, suitability=None)

    first = _text(report_pdf.build_pdf(context))[0]

    assert "no job-related questions" in first and "Strong fit" not in first


def test_every_value_is_escaped() -> None:
    html = report_pdf.report_html(_context(summary="<b>bold</b> & <script>x</script>"))

    assert "&lt;script&gt;" in html and "<script>" not in html


def test_dates_are_in_the_interviewers_time_zone() -> None:
    session = SimpleNamespace(
        started_at=START,
        ended_at=START + timedelta(minutes=47),
        scheduled_start=START,
        scheduled_end=START,
        candidate=SimpleNamespace(full_name="Rakib Hossain"),
    )
    assessment = Assessment(status="draft", qa_evaluations=PAIRS, coverage_map=COVERAGE)
    job = SimpleNamespace(title="Backend Engineer", job_code="HL-BE-01")

    dhaka = report_pdf.report_context(assessment, session, job, "Asia/Dhaka")
    unknown = report_pdf.report_context(assessment, session, job, "Not/AZone")

    assert dhaka["interview_when"] == "Tue 13 Oct 2026, 2:00 PM – 2:47 PM"
    assert unknown["interview_when"] == "Tue 13 Oct 2026, 8:00 AM – 8:47 AM"
    assert dhaka["answers_evaluated"] == 4


def test_the_file_name_holds_no_personal_data() -> None:
    assert report_pdf.file_name("HL BE/01", START) == "assessment_HL-BE-01_2026-10-13.pdf"


def test_a_report_must_be_written_first(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        evaluation_service, "get_assessment", lambda db, sid: Assessment(status="analysed")
    )

    with pytest.raises(ConflictError) as error:
        evaluation_service.report_file(None, 9, None)

    assert error.value.message == evaluation_service.NO_REPORT


def _auth(role: UserRole) -> dict[str, str]:
    token = create_access_token(subject="1", role=role, expires_in=timedelta(minutes=5))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    seen: list[str | None] = []

    def report_file(db, sid, time_zone):
        seen.append(time_zone)
        return b"%PDF-1.7 test", "assessment_HL-BE-01_2026-10-13.pdf"

    monkeypatch.setattr(evaluation_service, "report_file", report_file)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: None
    test_client = TestClient(app)
    test_client.seen = seen
    return test_client


def test_interviewer_downloads_the_report(client: TestClient) -> None:
    response = client.get(
        "/interviews/9/assessment/report.pdf?tz=Asia/Dhaka",
        headers=_auth(UserRole.INTERVIEWER),
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert 'filename="assessment_HL-BE-01_2026-10-13.pdf"' in response.headers[
        "content-disposition"
    ]
    assert response.content.startswith(b"%PDF") and client.seen == ["Asia/Dhaka"]


def test_candidate_cannot_download_a_report(client: TestClient) -> None:
    response = client.get(
        "/interviews/9/assessment/report.pdf", headers=_auth(UserRole.CANDIDATE)
    )

    assert response.status_code == 403
