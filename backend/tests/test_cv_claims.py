"""Tests for the CV claim check (F8): the claims taken from the CV, the check
of the AI's results, the claim nodes of the Final Assessment graph, the
claims-only run and the interviewer's marks. No test calls the real AI, and
the database is replaced with stand-ins."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from app.core.errors import ConflictError, NotFoundError, ServiceUnavailableError
from app.core.security import create_access_token
from app.db.session import get_db
from app.graphs.base import MAX_ATTEMPTS, thread_config
from app.graphs.final_assessment import claims as cv_claims
from app.graphs.final_assessment import graph as final
from app.graphs.final_assessment.claims import ClaimResultOut, ClaimsAnswer
from app.main import create_app
from app.models import Assessment
from app.models.enums import UserRole
from app.schemas.assessment import ClaimReviewRequest
from app.services import evaluation_service
from tests.test_final_assessment import CONFIG, GOOD_REPORT, PAIRS, TURNS, FakeAI, FakeStore

TURNS_BY_ID = {turn["id"]: turn for turn in TURNS}

CV = {
    "summary": "Backend engineer.",
    "skills": ["FastAPI", "pytest", "fastapi"],
    "experience": [
        {
            "title": "Backend Engineer",
            "company": "Acme",
            "start": "2021",
            "end": "Present",
            "description": "Wrote automated tests for every endpoint; reach me at x@y.com",
        }
    ],
    "total_experience_years": 4,
    "education": [
        {"degree": "BSc", "field": "Computer Science", "institution": "", "year": "2019"}
    ],
    "certifications": ["AWS Developer"],
    "projects": [
        {"name": "Shop API", "description": "An online shop API", "technologies": ["FastAPI"]}
    ],
}
CLAIMS = cv_claims.extract_claims(CV)


def _item(claim_id: str, result: str, question=None, quote=None, reason=None):
    return ClaimResultOut(
        claim_id=claim_id, result=result, question_id=question, quote=quote, reason=reason
    )


def _answer(*items: ClaimResultOut) -> ClaimsAnswer:
    """The given results, and not discussed for every other claim."""
    given = {item.claim_id for item in items}
    rest = [_item(claim["id"], "not_discussed") for claim in CLAIMS if claim["id"] not in given]
    return ClaimsAnswer(results=[*items, *rest])


CONTRADICTION = _item(
    "C2", "contradiction", "Q5", "not written tests", "Said they have not written tests."
)
CONSISTENT = _item("C6", "consistent", "Q2", "runs a function before the endpoint")
GOOD_CLAIMS = _answer(CONTRADICTION, CONSISTENT)


# --- The claims in the CV ----------------------------------------------------


def test_every_claim_in_the_cv_is_taken_in_order() -> None:
    assert [(claim["id"], claim["section"], claim["title"]) for claim in CLAIMS] == [
        ("C1", "total_experience", "4 years of professional work"),
        ("C2", "work_experience", "Backend Engineer, Acme"),
        ("C3", "project", "Shop API"),
        ("C4", "certification", "AWS Developer"),
        ("C5", "education", "BSc in Computer Science"),
        ("C6", "skill", "FastAPI"),
        ("C7", "skill", "pytest"),
    ]


def test_each_claim_keeps_its_cv_wording_and_where_it_is() -> None:
    by_id = {claim["id"]: claim for claim in CLAIMS}

    assert by_id["C1"]["cv_text"] == "Backend Engineer, Acme · 2021 – Present"
    assert by_id["C2"]["detail"] == "Backend Engineer, Acme · 2021 – Present"
    assert by_id["C5"]["cv_text"] == "BSc in Computer Science, 2019"
    assert by_id["C3"]["detail"] == "FastAPI"


def test_contact_details_in_the_cv_are_masked() -> None:
    assert all("x@y.com" not in claim["cv_text"] for claim in CLAIMS)


def test_a_cv_without_facts_has_no_claims() -> None:
    assert cv_claims.extract_claims(None) == []
    assert cv_claims.extract_claims({"skills": [], "total_experience_years": 0}) == []


def test_one_year_is_singular() -> None:
    claims = cv_claims.extract_claims({"total_experience_years": 1, "experience": []})

    assert claims[0]["title"] == "1 year of professional work"


# --- The check ---------------------------------------------------------------


def test_results_with_quotes_in_the_answer_are_used() -> None:
    accepted, problems = cv_claims.check_answer(GOOD_CLAIMS, CLAIMS, PAIRS, TURNS_BY_ID)

    assert not problems and len(accepted) == len(CLAIMS)
    contradiction = accepted["C2"]
    assert contradiction["result"] == "contradiction"
    assert contradiction["question"] == "How do you approach testing?"
    assert contradiction["turn_id"] == 4 and contradiction["start_ms"] == 25000
    assert contradiction["quote"] == "not written tests" and contradiction["review"] is None
    assert accepted["C6"]["quote"] == "runs a function before the endpoint"
    assert accepted["C1"]["result"] == "not_discussed" and accepted["C1"]["quote"] is None


@pytest.mark.parametrize(
    ("item", "problem"),
    [
        (_item("C2", "contradiction", "Q5", "I never said this", "Neutral."), "quote_not_found"),
        (_item("C2", "contradiction", "Q9", "not written tests", "Neutral."), "unknown_question"),
        (_item("C2", "contradiction", "Q3", "anything", "Neutral."), "unknown_question"),
        (_item("C2", "contradiction", "Q5", "not written tests"), "reason_missing"),
        (
            _item("C2", "contradiction", "Q5", "not written tests", "The CV is a lie."),
            "accusing_words",
        ),
        (
            _item("C3", "unverified", "Q2", "runs a function", "This looks fabricated."),
            "accusing_words",
        ),
    ],
)
def test_results_that_cannot_be_proven_are_problems(item: ClaimResultOut, problem: str) -> None:
    accepted, problems = cv_claims.check_answer(_answer(item), CLAIMS, PAIRS, TURNS_BY_ID)

    assert problem in problems[item.claim_id] and item.claim_id not in accepted


def test_a_claim_the_ai_left_out_is_a_problem() -> None:
    answer = ClaimsAnswer(results=GOOD_CLAIMS.results[1:])

    _, problems = cv_claims.check_answer(answer, CLAIMS, PAIRS, TURNS_BY_ID)

    assert problems == {"C2": ["claim_missing"]}


def test_a_misspelled_quote_keeps_the_transcript_words() -> None:
    item = _item("C6", "consistent", "Q2", "it runs a funktion before the endpoint")

    accepted, _ = cv_claims.check_answer(_answer(item), CLAIMS, PAIRS, TURNS_BY_ID)

    assert accepted["C6"]["quote"] == "It runs a function before the endpoint"


def test_the_ai_never_sees_contact_details_or_the_name() -> None:
    prompt_claims = cv_claims.claim_lines(CLAIMS)
    prompt_answers = cv_claims.answer_lines(PAIRS, TURNS_BY_ID)

    assert "x@y.com" not in prompt_claims and "a@b.com" not in prompt_answers
    assert "Q3" not in prompt_answers  # not answered, so nothing to compare


def test_open_contradictions_count_only_unmarked_ones() -> None:
    accepted, _ = cv_claims.check_answer(GOOD_CLAIMS, CLAIMS, PAIRS, TURNS_BY_ID)
    checks = cv_claims.claim_checks(CLAIMS, accepted)

    assert checks["status"] == "checked" and cv_claims.open_contradictions(checks) == 1
    checks["claims"][1]["review"] = {"status": "dismissed"}
    assert cv_claims.open_contradictions(checks) == 0
    assert cv_claims.open_contradictions(None) == 0


# --- The graph ---------------------------------------------------------------


class FakeClaimsAI:
    """Answers in turn; an exception in the list is raised instead."""

    def __init__(self, answers: list) -> None:
        self.answers = answers
        self.calls: list[dict] = []

    def __call__(self, job_title, claims, pairs, turns, problems=None):
        self.calls.append({"claims": [claim["id"] for claim in claims], "problems": problems})
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def _run(
    monkeypatch: pytest.MonkeyPatch,
    claim_answers: list,
    report_answers: list | None = None,
    claims_only: bool = False,
    store: FakeStore | None = None,
):
    store = store or FakeStore()
    store.results = {**store.results, "cv": CV}
    store.install(monkeypatch)
    report_ai = FakeAI(report_answers if report_answers is not None else [GOOD_REPORT])
    claims_ai = FakeClaimsAI(claim_answers)
    monkeypatch.setattr(final.report, "ask_ai", report_ai)
    monkeypatch.setattr(final.cv_claims, "ask_ai", claims_ai)
    graph = final.build_final_assessment_graph(InMemorySaver())
    state = {"session_id": 9, "claims_only": True} if claims_only else {"session_id": 9}
    graph.invoke(state, CONFIG)
    return graph, store, claims_ai, report_ai


def test_the_claims_are_checked_and_saved_before_the_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph, store, claims_ai, report_ai = _run(monkeypatch, [GOOD_CLAIMS])

    checks = store.claim_checks[0]
    assert checks["status"] == "checked"
    assert [claim["result"] for claim in checks["claims"][:2]] == [
        "not_discussed",
        "contradiction",
    ]
    assert claims_ai.calls == [{"claims": [c["id"] for c in CLAIMS], "problems": []}]
    # The report is written as before, without the claims.
    assert store.drafts and len(report_ai.calls) == 1
    assert "claim_checks" not in store.drafts[0]
    assert final.is_waiting_for_review(graph, CONFIG)


def test_claims_are_judged_in_batches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cv_claims, "BATCH_SIZE", 3)

    _, store, claims_ai, _ = _run(monkeypatch, [GOOD_CLAIMS] * 3)

    assert [len(call["claims"]) for call in claims_ai.calls] == [3, 3, 1]
    assert store.claim_checks[0]["status"] == "checked"


def test_claims_that_cannot_be_proven_are_asked_for_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wrong = _answer(_item("C2", "contradiction", "Q5", "I never said this", "Neutral."))

    _, store, claims_ai, _ = _run(monkeypatch, [wrong, GOOD_CLAIMS])

    assert claims_ai.calls[1] == {"claims": ["C2"], "problems": ["quote_not_found"]}
    assert store.claim_checks[0]["claims"][1]["result"] == "contradiction"


def test_claims_still_unproven_after_the_last_attempt_are_not_checked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wrong = _answer(_item("C2", "contradiction", "Q5", "I never said this", "Neutral."))

    _, store, claims_ai, _ = _run(monkeypatch, [wrong] * MAX_ATTEMPTS)

    assert len(claims_ai.calls) == MAX_ATTEMPTS
    claims = store.claim_checks[0]["claims"]
    assert claims[1]["result"] == "not_checked" and claims[1]["quote"] is None
    assert claims[0]["result"] == "not_discussed"


def test_an_unavailable_ai_saves_the_claims_as_not_checked_and_writes_the_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph, store, _, report_ai = _run(monkeypatch, [ServiceUnavailableError("down")])

    assert store.claim_checks[0] == {
        "status": "not_checked",
        "checked_at": store.claim_checks[0]["checked_at"],
        "claims": [],
    }
    assert store.drafts and final.is_waiting_for_review(graph, CONFIG)


def test_without_any_answer_every_claim_is_not_discussed_without_the_ai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeStore()
    store.results = {
        **store.results,
        "pairs": [{**pair, "answer_turn_ids": []} for pair in PAIRS],
    }

    _, store, claims_ai, _ = _run(
        monkeypatch, [], report_answers=[GOOD_REPORT] * MAX_ATTEMPTS, store=store
    )

    assert not claims_ai.calls
    assert {claim["result"] for claim in store.claim_checks[0]["claims"]} == {"not_discussed"}


def test_the_claims_only_run_leaves_the_report_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    graph, store, _, report_ai = _run(monkeypatch, [GOOD_CLAIMS], claims_only=True)

    assert store.claim_checks[0]["status"] == "checked"
    assert not store.drafts and not report_ai.calls and not store.approved
    assert not final.is_waiting_for_review(graph, CONFIG)
    assert "interview_score" not in graph.get_state(CONFIG).values


def test_the_claims_only_run_has_its_own_thread() -> None:
    assert final.claims_thread_id(9) != final.thread_id(9)


# --- The service -------------------------------------------------------------


def _assessment(status: str = "approved", checks: dict | None = None) -> Assessment:
    return Assessment(id=1, session_id=9, candidate_id=5, status=status, claim_checks=checks)


@pytest.mark.parametrize(
    ("assessment", "message"),
    [
        (_assessment("analysed"), evaluation_service.NO_REPORT),
        (
            _assessment(checks={"status": "checked", "checked_at": "x", "claims": []}),
            evaluation_service.CLAIMS_CHECKED,
        ),
    ],
)
def test_claims_are_checked_only_when_needed(
    monkeypatch: pytest.MonkeyPatch, assessment: Assessment, message: str
) -> None:
    monkeypatch.setattr(
        evaluation_service.session_service, "get_session", lambda db, sid: SimpleNamespace()
    )
    monkeypatch.setattr(evaluation_service, "get_assessment", lambda db, sid: assessment)

    with pytest.raises(ConflictError) as error:
        evaluation_service.start_claim_check(None, None, None, 9, 1)

    assert error.value.message == message


class FakeClaimsGraph:
    """The claims-only run: stores what it was given and what it ends with."""

    checkpointer = None

    def __init__(self, values: dict) -> None:
        self.values = values
        self.runs: list[tuple[dict, dict]] = []

    def invoke(self, state: dict, config: dict) -> None:
        self.runs.append((state, config))

    def get_state(self, config: dict):
        return SimpleNamespace(values=self.values)


def _progress():
    progress = SimpleNamespace(task_id="t", updates=[], notes=[])
    progress.update = lambda current, total, message=None: progress.updates.append(message)
    progress.note = lambda details: progress.notes.append(details)
    return progress


def test_the_claims_only_run_is_marked_for_the_screens() -> None:
    graph, progress = FakeClaimsGraph({}), _progress()

    summary = evaluation_service.run_claim_check(graph, 9, progress)

    state, config = graph.runs[0]
    assert state == {"session_id": 9, "claims_only": True}
    assert config == thread_config("cv-claims-9")
    assert summary["claims_only"] and progress.notes[0]["claims_only"]
    assert "Interview 1 of 1 · checking CV claims" in progress.updates


def test_a_claim_check_the_ai_could_not_do_fails_with_the_reason() -> None:
    progress = _progress()

    with pytest.raises(evaluation_service.EvaluationFailed) as error:
        evaluation_service.run_claim_check(FakeClaimsGraph({"claims_failed": True}), 9, progress)

    assert error.value.message == evaluation_service.CLAIMS_NOT_CHECKED
    assert progress.notes[-1]["failures"][0]["session_id"] == 9


class FakeDB:
    def __init__(self) -> None:
        self.committed = 0

    def get(self, model, key):
        return SimpleNamespace(id=key, full_name="Demo Interviewer")

    def commit(self) -> None:
        self.committed += 1

    def refresh(self, assessment) -> None:
        pass


def _checked() -> dict:
    accepted, _ = cv_claims.check_answer(GOOD_CLAIMS, CLAIMS, PAIRS, TURNS_BY_ID)
    return cv_claims.claim_checks(CLAIMS, accepted)


def _mark(monkeypatch, assessment, claim_id: str, body: dict, db=None):
    monkeypatch.setattr(evaluation_service, "get_assessment", lambda db, sid: assessment)
    return evaluation_service.review_claim(
        db or FakeDB(), 9, claim_id, ClaimReviewRequest(**body), user_id=1
    )


def test_a_contradiction_is_marked_checked_with_a_note(monkeypatch: pytest.MonkeyPatch) -> None:
    db = FakeDB()

    assessment = _mark(
        monkeypatch,
        _assessment(checks=_checked()),
        "C2",
        {"action": "checked", "note": "  Not a must-have.  "},
        db,
    )

    review = assessment.claim_checks["claims"][1]["review"]
    assert review["status"] == "checked" and review["note"] == "Not a must-have."
    assert review["by_name"] == "Demo Interviewer" and review["at"]
    assert db.committed == 1 and cv_claims.open_contradictions(assessment.claim_checks) == 0
    # Nothing else changes.
    assert assessment.claim_checks["claims"][5]["review"] is None


def test_a_mark_can_be_taken_away(monkeypatch: pytest.MonkeyPatch) -> None:
    assessment = _mark(monkeypatch, _assessment(checks=_checked()), "C2", {"action": "dismissed"})

    assessment = _mark(monkeypatch, assessment, "C2", {"action": "reopen"})

    assert assessment.claim_checks["claims"][1]["review"] is None


@pytest.mark.parametrize(
    ("checks", "claim_id", "error"),
    [
        (_checked(), "C6", ConflictError),
        (_checked(), "C99", NotFoundError),
        ({"status": "not_checked", "checked_at": "x", "claims": []}, "C2", ConflictError),
        (None, "C2", ConflictError),
    ],
)
def test_only_a_checked_contradiction_or_unverified_claim_is_marked(
    monkeypatch: pytest.MonkeyPatch, checks, claim_id: str, error: type
) -> None:
    with pytest.raises(error):
        _mark(monkeypatch, _assessment(checks=checks), claim_id, {"action": "checked"})


# --- The endpoints -----------------------------------------------------------


def _auth(role: UserRole) -> dict[str, str]:
    token = create_access_token(subject="1", role=role, expires_in=timedelta(minutes=5))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[final.get_final_assessment_graph] = lambda: SimpleNamespace()
    return TestClient(app)


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/interviews/9/assessment/claims", None),
        ("/interviews/9/assessment/claims/C2/review", {"action": "checked"}),
    ],
)
def test_candidate_cannot_reach_the_claims(client: TestClient, path: str, body) -> None:
    response = client.post(path, json=body, headers=_auth(UserRole.CANDIDATE))

    assert response.status_code == 403


def test_a_note_is_kept_short(client: TestClient) -> None:
    response = client.post(
        "/interviews/9/assessment/claims/C2/review",
        json={"action": "checked", "note": "x" * 501},
        headers=_auth(UserRole.INTERVIEWER),
    )

    assert response.status_code == 422
