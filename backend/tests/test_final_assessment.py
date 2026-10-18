"""Tests for the Final Assessment graph (scores, report, traceability check
and review), its service and its endpoint. No test calls the real AI, and
the database is replaced with stand-ins."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.core.errors import AppError, ConflictError, ServiceUnavailableError
from app.core.security import create_access_token
from app.db.session import get_db
from app.graphs.base import MAX_ATTEMPTS, thread_config
from app.graphs.final_assessment import findings, report, scoring
from app.graphs.final_assessment import graph as final
from app.graphs.final_assessment.report import ClaimOut, QuoteOut, ReportAnswer
from app.main import create_app
from app.models import Assessment, InterviewSession
from app.models.enums import UserRole
from app.schemas.assessment import ReviewRequest
from app.services import evaluation_service

NOW = datetime(2026, 10, 18, 10, 0, tzinfo=timezone.utc)

TURNS = [
    {"id": 1, "start_ms": 0, "text": "What does Depends do in FastAPI?"},
    {
        "id": 2,
        "start_ms": 5000,
        "text": "It runs a function before the endpoint, mail me at a@b.com.",
    },
    {"id": 3, "start_ms": 20000, "text": "How do you test an endpoint?"},
    {"id": 4, "start_ms": 25000, "text": "I have not written tests for that."},
    {"id": 5, "start_ms": 40000, "text": "What is our leave policy?"},
    {"id": 6, "start_ms": 45000, "text": "I think it is twenty days."},
]


def _evaluation(score: float, answered: str = "answered", **extra) -> dict:
    return {
        "answered": answered,
        "criteria": None,
        "score": score,
        "justification": "A reason.",
        "evidence": extra.pop("evidence", None),
        "accuracy_source": extra.pop("accuracy_source", None),
    }


PAIRS = [
    {
        "id": "Q1",
        "question": "Greeting",
        "question_turn_ids": [1],
        "answer_turn_ids": [],
        "start_ms": 0,
        "end_ms": 9000,
        "kind": "small_talk",
        "requirement_ids": [],
        "evaluation": None,
    },
    {
        "id": "Q2",
        "question": "What does Depends do in FastAPI?",
        "question_turn_ids": [1],
        "answer_turn_ids": [2],
        "start_ms": 0,
        "end_ms": 9000,
        "kind": "technical",
        "requirement_ids": ["R1"],
        "evaluation": _evaluation(
            86,
            evidence={"turn_id": 2, "start_ms": 5000, "quote": "runs a function"},
        ),
    },
    {
        "id": "Q3",
        "question": "How do you test an endpoint?",
        "question_turn_ids": [3],
        "answer_turn_ids": [],
        "start_ms": 20000,
        "end_ms": 29000,
        "kind": "technical",
        "requirement_ids": ["R2"],
        "evaluation": _evaluation(0, "not_answered"),
    },
    {
        "id": "Q4",
        "question": "What is our leave policy?",
        "question_turn_ids": [5],
        "answer_turn_ids": [6],
        "start_ms": 40000,
        "end_ms": 49000,
        "kind": "company",
        "requirement_ids": [],
        "evaluation": _evaluation(
            70,
            evidence={"turn_id": 6, "start_ms": 45000, "quote": "twenty days"},
            accuracy_source={"type": "not_checked"},
        ),
    },
    {
        "id": "Q5",
        "question": "How do you approach testing?",
        "question_turn_ids": [3],
        "answer_turn_ids": [4],
        "start_ms": 20000,
        "end_ms": 29000,
        "kind": "behavioural",
        "requirement_ids": [],
        "evaluation": _evaluation(
            45,
            evidence={"turn_id": 4, "start_ms": 25000, "quote": "not written tests"},
        ),
    },
]
INTERVIEW = round((86 + 0 + 70 + 45) / 4, 1)
OVERALL = round(0.4 * 80 + 0.6 * INTERVIEW, 1)


def _entry(rid: str, status: str, cv: str | None, **extra) -> dict:
    return {
        "requirement_id": rid,
        "text": {"R1": "FastAPI", "R2": "Testing", "R3": "Docker", "R4": "Kafka"}[rid],
        "priority": extra.pop("priority", "must_have"),
        "status": status,
        "average": extra.pop("average", None),
        "question_scores": extra.pop("question_scores", []),
        "mixed": extra.pop("mixed", False),
        "cv": {"status": cv, "evidence": f"CV says {rid}"} if cv else None,
    }


COVERAGE = [
    _entry(
        "R1", "covered", "met", average=86, question_scores=[{"pair_id": "Q2", "score": 86}]
    ),
    _entry("R2", "weak", "unmet", average=0, question_scores=[{"pair_id": "Q3", "score": 0}]),
    _entry("R3", "not_explored", "met"),
    _entry("R4", "not_explored", None, priority="preferred"),
]

TURNS_BY_ID = {turn["id"]: turn for turn in TURNS}


def _claim(text: str, questions=(), requirements=()) -> ClaimOut:
    return ClaimOut(
        text=text,
        questions=[QuoteOut(question_id=q, quote=quote) for q, quote in questions],
        requirements=list(requirements),
    )


GOOD_REPORT = ReportAnswer(
    summary="The candidate knows FastAPI well but has not tested endpoints.",
    strengths=[_claim("Clear grasp of FastAPI Depends", [("Q2", "runs a function")], ["R1"])],
    weaknesses=[_claim("No testing experience", [], ["R2"])],
)


# --- Scores and label --------------------------------------------------------


def test_the_interview_score_averages_evaluated_answers_only() -> None:
    assert scoring.interview_score(PAIRS) == INTERVIEW
    assert scoring.interview_score(PAIRS[:1]) is None


def test_the_overall_score_is_forty_percent_cv_and_sixty_percent_interview() -> None:
    assert scoring.overall_score(80, 50) == 62.0
    assert scoring.overall_score(None, 50) is None
    assert scoring.overall_score(80, None) is None


@pytest.mark.parametrize(
    ("overall", "label"),
    [
        (70, "strong_fit"),
        (69.9, "possible_fit"),
        (60, "possible_fit"),
        (59.9, "not_a_fit"),
        (None, None),
    ],
)
def test_the_label_follows_the_overall_score(overall: float | None, label: str | None) -> None:
    assert scoring.suitability(overall) == label
    assert Assessment(overall_score=overall).suitability == label


# --- Evidence gaps and areas to verify ---------------------------------------


def test_requirements_never_explored_are_gaps_with_must_haves_first() -> None:
    gaps = findings.evidence_gaps(list(reversed(COVERAGE)))

    assert [gap["id"] for gap in gaps] == ["G1", "G2"]
    assert gaps[0]["text"].startswith("R3 Docker (must-have)")
    assert gaps[0]["sources"][0] == {
        "type": "cv",
        "requirement_id": "R3",
        "requirement": "Docker",
        "status": "met",
        "evidence": "CV says R3",
    }
    assert gaps[1]["sources"][0]["status"] is None


def test_areas_to_verify_point_to_their_sources() -> None:
    areas = findings.areas_to_verify(PAIRS, COVERAGE)
    texts = [area["text"] for area in areas]

    assert texts[0].startswith("Ask about R3 Docker: the CV claims it")
    assert any("“How do you test an endpoint?” was not answered" in text for text in texts)
    assert any(
        "“What is our leave policy?”" in text and "not checked" in text for text in texts
    )
    unanswered = next(area for area in areas if "not answered" in area["text"])
    source = unanswered["sources"][0]
    assert source["turn_id"] == 3 and source["quote"] is None
    company = next(area for area in areas if "leave policy" in area["text"])
    assert company["sources"][0]["quote"] == "twenty days"


def test_a_poor_answer_behind_a_good_average_is_listed() -> None:
    entry = _entry(
        "R1",
        "covered",
        "met",
        average=65,
        mixed=True,
        question_scores=[{"pair_id": "Q2", "score": 86}, {"pair_id": "Q3", "score": 0}],
    )

    areas = findings.areas_to_verify(PAIRS, [entry])

    assert areas[0]["text"].startswith("Probe R1 FastAPI further")
    assert areas[0]["sources"][0]["pair_id"] == "Q3"


def test_an_interview_without_job_questions_says_so() -> None:
    areas = findings.areas_to_verify(PAIRS[:1], [])

    assert areas == [{"id": "V1", "text": findings.NO_JOB_QUESTIONS, "sources": []}]


# --- The traceability check --------------------------------------------------


def test_a_traced_report_has_no_problems() -> None:
    assert report.problems(GOOD_REPORT, PAIRS, COVERAGE, TURNS_BY_ID) == []


@pytest.mark.parametrize(
    ("strength", "claim", "problem"),
    [
        (True, _claim("Unsupported"), "no_source"),
        (True, _claim("Wrong id", [("Q9", "runs a function")]), "unknown_question"),
        (True, _claim("Small talk", [("Q1", "hello")]), "unknown_question"),
        (True, _claim("Made up", [("Q2", "uses dependency graphs")]), "quote_not_found"),
        (True, _claim("Weak", [("Q5", "not written tests")]), "strength_on_weak_answer"),
        (False, _claim("Good answer", [("Q2", "runs a function")]), "weakness_on_good_answer"),
        (True, _claim("CV unmet", [], ["R2"]), "cv_does_not_support"),
        (False, _claim("CV met", [], ["R1"]), "cv_does_not_support"),
        (True, _claim("Unknown", [], ["R9"]), "unknown_requirement"),
    ],
)
def test_untraced_claims_are_found(strength: bool, claim: ClaimOut, problem: str) -> None:
    answer = ReportAnswer(
        summary="A summary.",
        strengths=[claim] if strength else [],
        weaknesses=[] if strength else [claim],
    )

    assert problem in report.problems(answer, PAIRS, COVERAGE, TURNS_BY_ID)


def test_a_quote_may_differ_in_case_and_punctuation() -> None:
    claim = _claim("Fine", [("Q2", "Runs a function, before")])

    assert report.claim_problems(claim, True, {"Q2": PAIRS[1]}, {}, TURNS_BY_ID) == []


def test_only_traced_claims_are_kept_with_their_sources() -> None:
    answer = ReportAnswer(
        summary="  A summary.  ",
        strengths=[_claim("Made up", [("Q2", "not said")]), GOOD_REPORT.strengths[0]],
        weaknesses=GOOD_REPORT.weaknesses,
    )

    traced = report.traced_report(answer, PAIRS, COVERAGE, TURNS_BY_ID)

    assert traced["summary"] == "A summary." and traced["dropped"] == 1
    strength = traced["strengths"][0]
    assert strength["id"] == "S1"
    assert strength["sources"] == [
        {
            "type": "transcript",
            "pair_id": "Q2",
            "question": "What does Depends do in FastAPI?",
            "turn_id": 2,
            "start_ms": 5000,
            "quote": "runs a function",
        },
        findings.cv_source(COVERAGE[0]),
    ]
    assert traced["weaknesses"][0]["id"] == "W1"


def test_the_ai_never_sees_contact_details() -> None:
    lines = report.answer_lines(PAIRS, TURNS_BY_ID)

    assert "a@b.com" not in lines and "runs a function" in lines
    assert "Q1" not in lines


def test_a_request_for_changes_sends_the_draft_and_the_note() -> None:
    draft = {
        "summary": "Old summary.",
        "strengths": [{"text": "Old strength"}],
        "weaknesses": [],
    }

    text = report.revision_text(draft, "Mention his API design.")

    assert "Old summary." in text and "Old strength" in text
    assert "<interviewer_note>\nMention his API design.\n</interviewer_note>" in text
    assert report.revision_text(None, "note") == "" and report.revision_text(draft, None) == ""


# --- The graph ---------------------------------------------------------------


class FakeStore:
    def __init__(self, cv_score: float | None = 80.0) -> None:
        self.results = {
            "candidate_id": 5,
            "job_title": "Backend Engineer",
            "pairs": PAIRS,
            "coverage": COVERAGE,
            "cv_score": cv_score,
            "turns": TURNS,
        }
        self.drafts: list[dict] = []
        self.approved: list[tuple[int, int]] = []
        self.assessed: list[int] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(final.store, "load_results", lambda sid: self.results)
        monkeypatch.setattr(
            final.store, "save_draft", lambda sid, values: self.drafts.append(dict(values))
        )
        monkeypatch.setattr(
            final.store, "approve", lambda sid, uid: self.approved.append((sid, uid))
        )
        monkeypatch.setattr(final.store, "mark_assessed", self.assessed.append)


class FakeAI:
    """Answers in turn; an exception in the list is raised instead."""

    def __init__(self, answers: list) -> None:
        self.answers = answers
        self.calls: list[dict] = []

    def __call__(self, job_title, scores, pairs, coverage, turns, **kwargs):
        self.calls.append({"scores": scores, **kwargs})
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


CONFIG = thread_config("final-assessment-9")


def _start(monkeypatch: pytest.MonkeyPatch, answers: list, store: FakeStore | None = None):
    store = store or FakeStore()
    store.install(monkeypatch)
    ai = FakeAI(answers)
    monkeypatch.setattr(final.report, "ask_ai", ai)
    graph = final.build_final_assessment_graph(InMemorySaver())
    graph.invoke({"session_id": 9}, CONFIG)
    return graph, store, ai


def test_the_draft_is_saved_and_waits_for_review(monkeypatch: pytest.MonkeyPatch) -> None:
    graph, store, ai = _start(monkeypatch, [GOOD_REPORT])

    assert final.is_waiting_for_review(graph, CONFIG)
    draft = store.drafts[0]
    assert draft["cv_score"] == 80.0 and draft["interview_score"] == INTERVIEW
    assert draft["overall_score"] == OVERALL
    assert draft["summary"].startswith("The candidate knows FastAPI")
    assert [claim["id"] for claim in draft["strengths"]] == ["S1"]
    assert [gap["id"] for gap in draft["gaps"]] == ["G1", "G2"]
    assert draft["areas_to_verify"] and not store.approved
    assert ai.calls[0]["scores"] == {"cv": 80.0, "interview": INTERVIEW, "overall": OVERALL}


def test_an_untraced_report_is_asked_for_again(monkeypatch: pytest.MonkeyPatch) -> None:
    untraced = ReportAnswer(summary="S.", strengths=[_claim("Made up", [("Q2", "not said")])])

    graph, store, ai = _start(monkeypatch, [untraced, GOOD_REPORT])

    assert len(ai.calls) == 2 and ai.calls[1]["problems"] == ["quote_not_found"]
    assert store.drafts[0]["strengths"][0]["text"] == "Clear grasp of FastAPI Depends"


def test_claims_still_untraced_after_the_last_attempt_are_left_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    untraced = ReportAnswer(
        summary="S.",
        strengths=[_claim("Made up", [("Q2", "not said")]), GOOD_REPORT.strengths[0]],
    )

    graph, store, ai = _start(monkeypatch, [untraced] * MAX_ATTEMPTS)

    assert len(ai.calls) == MAX_ATTEMPTS
    assert [claim["text"] for claim in store.drafts[0]["strengths"]] == [
        "Clear grasp of FastAPI Depends"
    ]
    assert final.is_waiting_for_review(graph, CONFIG)


def test_an_unavailable_ai_writes_no_report(monkeypatch: pytest.MonkeyPatch) -> None:
    graph, store, _ = _start(monkeypatch, [ServiceUnavailableError("down")])

    assert graph.get_state(CONFIG).values["failure"] == final.AI_UNAVAILABLE
    assert not store.drafts and not final.is_waiting_for_review(graph, CONFIG)


def test_an_interview_not_analysed_writes_no_report(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(final.store, "load_results", lambda sid: None)
    graph = final.build_final_assessment_graph(InMemorySaver())

    result = graph.invoke({"session_id": 9}, CONFIG)

    assert result["failure"] == final.NOT_ANALYSED


def test_approving_saves_the_report_and_assesses_the_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph, store, _ = _start(monkeypatch, [GOOD_REPORT])

    graph.invoke(Command(resume={"action": "approve", "user_id": 1}), CONFIG)

    assert store.approved == [(9, 1)] and store.assessed == [5]
    assert graph.get_state(CONFIG).next == ()


def test_a_request_for_changes_rewrites_the_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    rewritten = GOOD_REPORT.model_copy(update={"summary": "A new summary."})
    graph, store, ai = _start(monkeypatch, [GOOD_REPORT, rewritten])

    graph.invoke(
        Command(resume={"action": "request_changes", "note": "Shorter.", "user_id": 1}),
        CONFIG,
    )

    assert ai.calls[1]["note"] == "Shorter."
    assert ai.calls[1]["draft"]["summary"].startswith("The candidate knows FastAPI")
    assert store.drafts[-1]["summary"] == "A new summary."
    assert final.is_waiting_for_review(graph, CONFIG) and not store.approved


def test_an_unavailable_ai_keeps_the_draft_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    graph, store, _ = _start(monkeypatch, [GOOD_REPORT, ServiceUnavailableError("down")])

    graph.invoke(
        Command(resume={"action": "request_changes", "note": "Shorter.", "user_id": 1}),
        CONFIG,
    )

    assert graph.get_state(CONFIG).values["revision_failed"] is True
    assert final.is_waiting_for_review(graph, CONFIG) and len(store.drafts) == 1


def test_an_edit_changes_the_summary_and_removes_points(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph, store, ai = _start(monkeypatch, [GOOD_REPORT])

    graph.invoke(
        Command(
            resume={"action": "edit", "summary": "My words.", "remove": ["W1"], "user_id": 1}
        ),
        CONFIG,
    )

    draft = store.drafts[-1]
    assert draft["summary"] == "My words." and draft["weaknesses"] == []
    assert len(draft["strengths"]) == 1 and len(ai.calls) == 1
    assert final.is_waiting_for_review(graph, CONFIG)


# --- The review request, service and endpoint --------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {"action": "request_changes"},
        {"action": "request_changes", "note": "   "},
        {"action": "edit"},
        {"action": "edit", "summary": "  ", "remove": []},
    ],
)
def test_a_review_needs_what_its_action_uses(body: dict) -> None:
    with pytest.raises(ValueError):
        ReviewRequest(**body)


class FakeReviewGraph:
    def __init__(self, waiting: bool = True, revision_failed: bool = False) -> None:
        self.waiting = waiting
        self.revision_failed = revision_failed
        self.resumed: list[dict] = []

    def get_state(self, config: dict):
        return SimpleNamespace(
            next=("human_review",) if self.waiting else (),
            values={"revision_failed": self.revision_failed},
        )

    def invoke(self, command: Command, config: dict) -> None:
        self.resumed.append(command.resume)


class FakeDB:
    def refresh(self, assessment) -> None:
        pass


def _draft(status: str = "draft") -> Assessment:
    return Assessment(
        session_id=9,
        status=status,
        strengths=[{"id": "S1", "text": "x", "sources": []}],
        weaknesses=[{"id": "W1", "text": "y", "sources": []}],
    )


def _review(monkeypatch: pytest.MonkeyPatch, assessment: Assessment, graph, body: dict):
    monkeypatch.setattr(evaluation_service, "get_assessment", lambda db, sid: assessment)
    return evaluation_service.review_assessment(
        FakeDB(), graph, 9, ReviewRequest(**body), user_id=1
    )


def test_the_review_continues_the_paused_report(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = FakeReviewGraph()

    _review(monkeypatch, _draft(), graph, {"action": "edit", "remove": ["W1"]})

    assert graph.resumed[0]["action"] == "edit" and graph.resumed[0]["remove"] == ["W1"]
    assert graph.resumed[0]["user_id"] == 1


@pytest.mark.parametrize(
    ("assessment", "graph"),
    [(_draft("approved"), FakeReviewGraph()), (_draft(), FakeReviewGraph(waiting=False))],
)
def test_only_a_waiting_draft_can_be_reviewed(
    monkeypatch: pytest.MonkeyPatch, assessment: Assessment, graph: FakeReviewGraph
) -> None:
    with pytest.raises(ConflictError) as error:
        _review(monkeypatch, assessment, graph, {"action": "approve"})

    assert error.value.message == evaluation_service.NOT_A_DRAFT and not graph.resumed


def test_only_points_in_the_report_can_be_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(AppError) as error:
        _review(monkeypatch, _draft(), FakeReviewGraph(), {"action": "edit", "remove": ["S9"]})

    assert error.value.message == evaluation_service.UNKNOWN_POINT


def test_a_rewrite_the_ai_could_not_do_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ServiceUnavailableError):
        _review(
            monkeypatch,
            _draft(),
            FakeReviewGraph(revision_failed=True),
            {"action": "request_changes", "note": "More detail."},
        )


def _auth(role: UserRole) -> dict[str, str]:
    token = create_access_token(subject="1", role=role, expires_in=timedelta(minutes=5))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    def review(db, graph, sid, payload, uid):
        return Assessment(
            id=1,
            session_id=sid,
            candidate_id=5,
            status="approved" if payload.action == "approve" else "draft",
            qa_evaluations=PAIRS,
            coverage_map=COVERAGE,
            question_suggestions=None,
            cv_score=80.0,
            interview_score=52.0,
            overall_score=63.2,
            report="A summary.",
            strengths=[
                {
                    "id": "S1",
                    "text": "Clear grasp of Depends",
                    "sources": [findings.transcript_source(PAIRS[1])],
                }
            ],
            weaknesses=[],
            gaps=findings.evidence_gaps(COVERAGE),
            areas_to_verify=findings.areas_to_verify(PAIRS, COVERAGE),
            approved_at=NOW if payload.action == "approve" else None,
            created_at=NOW,
            updated_at=NOW,
        )

    monkeypatch.setattr(evaluation_service, "review_assessment", review)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[final.get_final_assessment_graph] = lambda: SimpleNamespace()
    return TestClient(app)


def test_interviewer_approves_the_report(client: TestClient) -> None:
    response = client.post(
        "/interviews/9/assessment/review",
        json={"action": "approve"},
        headers=_auth(UserRole.INTERVIEWER),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved" and body["suitability"] == "possible_fit"
    assert body["strengths"][0]["sources"][0]["quote"] == "runs a function"
    assert body["gaps"][0]["sources"][0]["type"] == "cv"


def test_a_request_for_changes_needs_a_note(client: TestClient) -> None:
    response = client.post(
        "/interviews/9/assessment/review",
        json={"action": "request_changes"},
        headers=_auth(UserRole.INTERVIEWER),
    )

    assert response.status_code == 422


def test_candidate_cannot_review_a_report(client: TestClient) -> None:
    response = client.post(
        "/interviews/9/assessment/review",
        json={"action": "approve"},
        headers=_auth(UserRole.CANDIDATE),
    )

    assert response.status_code == 403


# --- The job's ranked list ---------------------------------------------------


def _completed(
    sid: int, name: str, status: str | None, overall: float | None, interview: float | None
):
    session = InterviewSession(
        id=sid,
        job_id=2,
        candidate_id=sid,
        status="completed",
        scheduled_start=NOW,
        started_at=NOW - timedelta(days=sid),
    )
    session.__dict__["candidate"] = SimpleNamespace(
        full_name=name, scores={"final_score": 80.0}
    )
    assessment = None
    if status:
        assessment = Assessment(
            status=status,
            qa_evaluations=PAIRS,
            coverage_map=COVERAGE,
            cv_score=80.0 if status != "analysed" else None,
            interview_score=interview,
            overall_score=overall,
            strengths=[] if status != "analysed" else None,
        )
    session.__dict__["assessment"] = assessment
    return session


class FakeRankingDB:
    def __init__(self, sessions: list) -> None:
        self.sessions = sessions

    def get(self, model, key):
        return SimpleNamespace(id=key)

    def scalars(self, query):
        return SimpleNamespace(all=lambda: self.sessions)


def test_candidates_are_ranked_by_overall_score_then_interview_then_name() -> None:
    sessions = [
        _completed(1, "Bina", "approved", 64.0, 52.7),
        _completed(2, "Arif", "draft", 78.6, 75.7),
        _completed(3, "Chaya", "draft", 78.6, 80.0),
        _completed(4, "Dipu", "approved", 78.6, 80.0),
        _completed(5, "Esha", None, None, None),
        _completed(6, "Faruk", "analysed", None, None),
        _completed(7, "Gazi", "draft", None, None),
    ]

    rows = evaluation_service.ranked_assessments(FakeRankingDB(sessions), 2)

    assert [(row["candidate_name"], row["rank"]) for row in rows] == [
        ("Chaya", 1),
        ("Dipu", 2),
        ("Arif", 3),
        ("Bina", 4),
        ("Esha", None),
        ("Faruk", None),
        ("Gazi", None),
    ]
    first = rows[0]
    assert first["suitability"] == "strong_fit" and first["status"] == "draft"
    assert first["answers_evaluated"] == 4
    assert first["coverage"] == {"covered": 1, "weak": 1, "not_explored": 2, "total": 4}


def test_an_unevaluated_interview_shows_the_screening_score_only() -> None:
    rows = evaluation_service.ranked_assessments(
        FakeRankingDB([_completed(5, "Esha", None, None, None)]), 2
    )

    row = rows[0]
    assert row["cv_score"] == 80.0 and row["overall_score"] is None
    assert row["coverage"] is None and row["answers_evaluated"] == 0


def test_an_analysis_without_a_report_has_no_report_points() -> None:
    rows = evaluation_service.ranked_assessments(
        FakeRankingDB([_completed(6, "Faruk", "analysed", None, None)]), 2
    )

    assert rows[0]["strengths"] is None and rows[0]["status"] == "analysed"


def test_interviewer_reads_the_ranked_list(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = evaluation_service._ranked_row(_completed(2, "Arif", "draft", 78.6, 75.7))
    monkeypatch.setattr(
        evaluation_service, "ranked_assessments", lambda db, job_id: [{**row, "rank": 1}]
    )

    response = client.get("/jobs/2/assessments", headers=_auth(UserRole.INTERVIEWER))
    refused = client.get("/jobs/2/assessments", headers=_auth(UserRole.CANDIDATE))

    assert response.status_code == 200
    first = response.json()[0]
    assert first["rank"] == 1 and first["suitability"] == "strong_fit"
    assert refused.status_code == 403


# --- Writing only the report -------------------------------------------------


def test_a_report_is_written_for_evaluated_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    progress = SimpleNamespace(task_id="t", updates=[], notes=[])
    progress.update = lambda current, total, message=None: progress.updates.append(message)
    progress.note = lambda details: progress.notes.append(details)
    written: list[int] = []

    def write(graph, sid):
        written.append(sid)
        return {}

    monkeypatch.setattr(evaluation_service, "write_report", write)

    summary = evaluation_service.run_report(None, 9, progress)

    assert written == [9] and summary["evaluated"] == 1
    assert "Interview 1 of 1 · writing the report" in progress.updates
    assert progress.notes[0]["current"] == 9 and progress.notes[-1]["current"] is None


def test_a_report_that_cannot_be_written_fails_with_the_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    progress = SimpleNamespace(task_id="t", update=lambda *args: None, notes=[])
    progress.note = lambda details: progress.notes.append(details)
    monkeypatch.setattr(
        evaluation_service,
        "write_report",
        lambda graph, sid: {"failure": final.AI_UNAVAILABLE},
    )

    with pytest.raises(evaluation_service.EvaluationFailed) as error:
        evaluation_service.run_report(None, 9, progress)

    assert error.value.message == final.AI_UNAVAILABLE
    failure = {"session_id": 9, "reason": final.AI_UNAVAILABLE}
    assert progress.notes[-1]["failures"] == [failure]


def test_only_an_interview_without_a_report_gets_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        evaluation_service.session_service,
        "get_session",
        lambda db, sid: SimpleNamespace(job_id=2),
    )
    monkeypatch.setattr(evaluation_service, "get_assessment", lambda db, sid: _draft())

    with pytest.raises(ConflictError) as error:
        evaluation_service.start_report(None, None, None, 9, 1)

    assert error.value.message == evaluation_service.HAS_REPORT


# --- Approving all drafts ----------------------------------------------------


class FakeDraftsDB:
    def __init__(self, session_ids: list[int]) -> None:
        self.session_ids = session_ids

    def get(self, model, key):
        return SimpleNamespace(id=key)

    def scalars(self, query):
        return SimpleNamespace(all=lambda: self.session_ids)


class FakeWaitingGraph:
    """Waiting for review on the given interviews' threads."""

    def __init__(self, waiting: set[int]) -> None:
        self.waiting = waiting
        self.approved: list[tuple[str, dict]] = []

    def get_state(self, config: dict):
        session_id = int(config["configurable"]["thread_id"].rsplit("-", 1)[1])
        return SimpleNamespace(next=("human_review",) if session_id in self.waiting else ())

    def invoke(self, command: Command, config: dict) -> None:
        self.approved.append((config["configurable"]["thread_id"], command.resume))


def test_all_waiting_drafts_are_approved_and_the_rest_skipped() -> None:
    graph = FakeWaitingGraph({7, 9})

    result = evaluation_service.approve_all_drafts(FakeDraftsDB([7, 8, 9]), graph, 2, 1)

    assert result == {"approved": 2, "skipped": 1}
    assert [thread for thread, _ in graph.approved] == [
        "final-assessment-7",
        "final-assessment-9",
    ]
    assert graph.approved[0][1] == {"action": "approve", "user_id": 1}


def test_interviewer_approves_all_drafts(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        evaluation_service,
        "approve_all_drafts",
        lambda db, graph, job_id, uid: {"approved": 3, "skipped": 0},
    )

    response = client.post("/jobs/2/assessments/approve", headers=_auth(UserRole.INTERVIEWER))
    refused = client.post("/jobs/2/assessments/approve", headers=_auth(UserRole.CANDIDATE))

    assert response.status_code == 200 and response.json()["approved"] == 3
    assert refused.status_code == 403


def test_the_approver_is_named_next_to_the_report() -> None:
    from app.models.user import User

    assert Assessment().approved_by_name is None
    assert Assessment(approver=User(full_name="Demo Interviewer")).approved_by_name == (
        "Demo Interviewer"
    )
