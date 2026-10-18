"""Tests for the Q&A Analysis graph (question-answer segmentation), the
evaluation service and its endpoints. No test calls the real AI, and the
database is replaced with stand-ins."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from app.core.errors import AppError, ConflictError, ServiceUnavailableError
from app.core.security import create_access_token
from app.db.session import get_db
from app.graphs.base import MAX_ATTEMPTS, thread_config
from app.graphs.qa_analysis import graph as qa
from app.graphs.qa_analysis import coverage, evaluation, references, segmentation, suggestions
from app.graphs.qa_analysis.evaluation import Criterion, EvaluationAnswer, PairJudgement
from app.graphs.qa_analysis.segmentation import PairOut, SegmentationAnswer
from app.main import create_app
from app.models import Assessment, Document, InterviewSession, Task
from app.models.enums import SessionStatus, UserRole
from app.services import evaluation_service, knowledge_service

NOW = datetime(2026, 10, 18, 10, 0, tzinfo=timezone.utc)


def _turn(turn_id: int, speaker: str, start_s: int, text: str = "Some words.") -> dict:
    return {
        "id": turn_id,
        "speaker": speaker,
        "start_ms": start_s * 1000,
        "end_ms": start_s * 1000 + 4000,
        "text": text,
    }


TURNS = [
    _turn(1, "interviewer", 0, "Hello, thanks for joining."),
    _turn(2, "candidate", 5, "Thank you, happy to be here."),
    _turn(
        3,
        "interviewer",
        10,
        "Tell me about your Python experience, and how have you used Docker?",
    ),
    _turn(4, "candidate", 20, "I built REST APIs in FastAPI for two years."),
    _turn(5, "candidate", 30, "I use Docker Compose for local services."),
    _turn(6, "interviewer", 40, "Why did you pick FastAPI?"),
    _turn(7, "candidate", 45, "For its typing and speed."),
]


def _pair(
    question: str, q: list[int], a: list[int], kind: str = "technical", **extra
) -> PairOut:
    return PairOut(question=question, question_turns=q, answer_turns=a, kind=kind, **extra)


GOOD_ANSWER = SegmentationAnswer(
    pairs=[
        _pair("Greeting", [1], [2], "small_talk"),
        _pair("Python experience", [3], [4]),
        _pair("Docker use", [3], [5]),
        _pair("Why FastAPI", [6], [7], follow_up_of=2),
    ]
)


REQUIREMENTS = [
    {"id": "R1", "text": "Python web development", "priority": "must_have"},
    {"id": "R2", "text": "Docker", "priority": "preferred"},
    {"id": "R3", "text": "SQL databases", "priority": "must_have"},
]
CV_MATCHES = [
    {"id": "R1", "status": "met", "evidence": "FastAPI for two years"},
    {"id": "R3", "status": "met", "evidence": "PostgreSQL"},
]


# --- Segmentation checks ----------------------------------------------------


def test_pairs_keep_turns_and_times_and_split_multi_part_questions() -> None:
    pairs = segmentation.build_pairs(GOOD_ANSWER, TURNS)

    assert [pair["id"] for pair in pairs] == ["Q1", "Q2", "Q3", "Q4"]
    python, docker = pairs[1], pairs[2]
    assert python["question_turn_ids"] == docker["question_turn_ids"] == [3]
    assert python["answer_turn_ids"] == [4] and docker["answer_turn_ids"] == [5]
    assert docker["start_ms"] == 10_000 and docker["end_ms"] == 34_000
    assert pairs[0]["kind"] == "small_talk"


def test_a_follow_up_points_to_the_pair_it_follows() -> None:
    pairs = segmentation.build_pairs(GOOD_ANSWER, TURNS)

    assert pairs[3]["follow_up_of"] == "Q2"
    assert pairs[1]["follow_up_of"] is None


def test_unknown_turns_and_wrong_speakers_are_dropped() -> None:
    answer = SegmentationAnswer(
        pairs=[_pair("Python experience", [3, 4, 99], [4, 6, 5, 4])]
    )

    [pair] = segmentation.build_pairs(answer, TURNS)

    assert pair["question_turn_ids"] == [3]
    assert pair["answer_turn_ids"] == [4, 5]


def test_a_pair_without_a_real_question_turn_is_dropped() -> None:
    answer = SegmentationAnswer(
        pairs=[
            _pair("Made up", [99], [4]),
            _pair("Asked by the candidate", [2], [4]),
            _pair("   ", [3], [4]),
            _pair("Why FastAPI", [6], [7], follow_up_of=1),
        ]
    )

    [pair] = segmentation.build_pairs(answer, TURNS)

    # Renumbered, and its follow-up link is dropped with the pair it named.
    assert pair["id"] == "Q1" and pair["follow_up_of"] is None


def test_a_follow_up_cannot_point_forward() -> None:
    answer = SegmentationAnswer(
        pairs=[_pair("Python", [3], [4], follow_up_of=2), _pair("Why FastAPI", [6], [7])]
    )

    pairs = segmentation.build_pairs(answer, TURNS)

    assert pairs[0]["follow_up_of"] is None


def test_an_unanswered_question_is_kept() -> None:
    [pair] = segmentation.build_pairs(
        SegmentationAnswer(pairs=[_pair("Why FastAPI", [6], [])]), TURNS
    )

    assert pair["answer_turn_ids"] == [] and pair["end_ms"] == 44_000


def test_contact_details_are_masked_before_the_ai_sees_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts: list[str] = []

    def fake_ai(prompt: str, schema):
        prompts.append(prompt)
        return GOOD_ANSWER

    monkeypatch.setattr(segmentation.ai_client, "generate_structured", fake_ai)
    contact = "Mail me at sam.person@example.com or +880 1711 223344"
    turns = [*TURNS, _turn(8, "candidate", 50, contact)]

    segmentation.ask_ai("Backend Engineer", turns)

    assert "sam.person@example.com" not in prompts[0]
    assert "1711" not in prompts[0]
    assert "[email]" in prompts[0] and "[T8] Candidate (00:50):" in prompts[0]


def test_times_are_shown_from_the_start_of_the_interview() -> None:
    assert segmentation.clock(65_000) == "01:05"
    assert segmentation.clock(3_725_000) == "1:02:05"


def test_counts_leave_small_talk_out_of_the_evaluation() -> None:
    counts = segmentation.counts(segmentation.build_pairs(GOOD_ANSWER, TURNS))

    assert counts == {"pairs": 4, "evaluated": 3, "small_talk": 1}


# --- Requirements explored by each question ---------------------------------


def test_each_pair_keeps_only_the_jobs_own_requirement_ids() -> None:
    answer = SegmentationAnswer(
        pairs=[
            _pair("Greeting", [1], [2], "small_talk", requirements=["R1"]),
            _pair("Python experience", [3], [4], requirements=[" r1 ", "R9", "R1"]),
            _pair("Docker use", [3], [5], requirements=["R2", "R1"]),
        ]
    )

    pairs = segmentation.build_pairs(answer, TURNS, ["R1", "R2", "R3"])

    assert [pair["requirement_ids"] for pair in pairs] == [[], ["R1"], ["R1", "R2"]]


def test_the_ai_is_given_the_jobs_requirements(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts: list[str] = []
    monkeypatch.setattr(
        segmentation.ai_client,
        "generate_structured",
        lambda prompt, schema: prompts.append(prompt) or GOOD_ANSWER,
    )

    segmentation.ask_ai("Backend Engineer", TURNS, REQUIREMENTS)

    assert "R1 (must-have): Python web development" in prompts[0]
    assert "R2 (preferred): Docker" in prompts[0]


# --- Requirement coverage ---------------------------------------------------


def _scored(pair_id: str, requirement_ids: list[str], score: float | None) -> dict:
    evaluation_part = None if score is None else {"score": score}
    return {"id": pair_id, "requirement_ids": requirement_ids, "evaluation": evaluation_part}


def test_each_requirement_gets_its_questions_average_and_status() -> None:
    pairs = [
        _scored("Q2", ["R1"], 86.0),
        _scored("Q3", ["R1", "R2"], 70.0),
        _scored("Q4", ["R2"], 30.0),
    ]

    result = {
        entry["requirement_id"]: entry
        for entry in coverage.map_coverage(pairs, REQUIREMENTS, CV_MATCHES)
    }

    assert result["R1"]["status"] == "covered" and result["R1"]["average"] == 78.0
    assert result["R1"]["question_scores"] == [
        {"pair_id": "Q2", "score": 86.0},
        {"pair_id": "Q3", "score": 70.0},
    ]
    assert result["R2"]["status"] == "weak" and result["R2"]["average"] == 50.0
    assert result["R3"]["status"] == "not_explored" and result["R3"]["average"] is None
    assert result["R3"]["priority"] == "must_have"


def test_the_cv_result_is_shown_next_to_each_requirement() -> None:
    result = coverage.map_coverage([], REQUIREMENTS, CV_MATCHES)

    assert result[2]["cv"] == {"status": "met", "evidence": "PostgreSQL"}
    assert result[1]["cv"] is None
    assert coverage.map_coverage([], REQUIREMENTS, None)[0]["cv"] is None


def test_a_covered_requirement_with_a_poor_answer_is_marked_mixed() -> None:
    pairs = [_scored("Q2", ["R1"], 95.0), _scored("Q3", ["R1"], 35.0)]

    [r1, *_] = coverage.map_coverage(pairs, REQUIREMENTS, None)

    assert r1["status"] == "covered" and r1["mixed"] is True


def test_the_covered_line_is_sixty() -> None:
    at_line = coverage.map_coverage([_scored("Q2", ["R1"], 60.0)], REQUIREMENTS, None)
    below = coverage.map_coverage([_scored("Q2", ["R1"], 59.9)], REQUIREMENTS, None)

    assert at_line[0]["status"] == "covered" and below[0]["status"] == "weak"


def test_small_talk_never_counts_towards_a_requirement() -> None:
    result = coverage.map_coverage([_scored("Q1", ["R1"], None)], REQUIREMENTS, None)

    assert result[0]["status"] == "not_explored"
    assert coverage.counts(result) == {"covered": 0, "weak": 0, "not_explored": 3}


# --- Question bank suggestions -----------------------------------------------


def _offered(pair_id: str, question: str, kind: str = "technical", **extra) -> dict:
    return {
        "id": pair_id,
        "question": question,
        "kind": kind,
        "follow_up_of": None,
        "evaluation": {"answered": "answered"},
        **extra,
    }


def test_only_answered_standalone_job_questions_are_suggested() -> None:
    pairs = [
        _offered("Q1", "Greeting", "small_talk"),
        _offered("Q2", "How does FastAPI validate requests?"),
        _offered("Q3", "Why did you choose it?", follow_up_of="Q2"),
        _offered("Q4", "Explain database indexes", evaluation={"answered": "not_answered"}),
        _offered("Q5", "How does FastAPI validate requests?!"),
        _offered("Q6", "Tell me about a hard project", "behavioural"),
        _offered("Q7", "What do you know about our products?", "company"),
    ]

    assert [pair["id"] for pair in suggestions.candidates(pairs)] == ["Q2", "Q6", "Q7"]


def test_questions_already_in_the_bank_are_not_suggested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        suggestions, "in_bank", lambda question, role: "FastAPI" in question
    )
    pairs = [
        _offered("Q2", "How does FastAPI validate requests?"),
        _offered("Q3", "What is a JOIN?"),
    ]

    found = suggestions.suggest(pairs, "Backend Engineer")

    assert found == [
        {"pair_id": "Q3", "question": "What is a JOIN?", "kind": "technical", "added": False}
    ]


@pytest.mark.parametrize(("similarity", "duplicate"), [(0.85, True), (0.79, False)])
def test_a_very_similar_bank_question_counts_as_a_duplicate(
    monkeypatch: pytest.MonkeyPatch, similarity: float, duplicate: bool
) -> None:
    calls: list[tuple] = []

    def fake_call(server: str, tool: str, arguments: dict):
        calls.append((server, tool, arguments["role"]))
        found = [{"question": "q", "source": "bank.txt", "similarity": similarity}]
        return SimpleNamespace(is_error=False, structured_content={"result": found})

    monkeypatch.setattr(suggestions.mcp_client, "call_tool", fake_call)

    assert suggestions.in_bank("What is a JOIN?", "Backend Engineer") is duplicate
    assert calls == [("rag", "search_question_bank", "Backend Engineer")]


def test_a_question_bank_that_cannot_be_searched_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def down(*args):
        raise ConnectionError("down")

    monkeypatch.setattr(suggestions.mcp_client, "call_tool", down)

    with pytest.raises(suggestions.QuestionBankSearchError):
        suggestions.in_bank("What is a JOIN?", "Backend Engineer")


# --- Answer evaluation -------------------------------------------------------


PAIRS = segmentation.build_pairs(GOOD_ANSWER, TURNS)
TURNS_BY_ID = {turn["id"]: turn for turn in TURNS}
# The answer turn and quote each pair id is judged on. Q1 is used only when a
# test's transcript starts with a job-related question.
QUOTES = {
    "Q1": (7, "typing"),
    "Q2": (4, "REST APIs in FastAPI"),
    "Q3": (5, "Docker Compose"),
    "Q4": (7, "typing"),
}


def _criterion(score: int = 80) -> Criterion:
    return Criterion(score=score, reason="Clear and correct.")


def _judgement(pair_id: str, **changes) -> PairJudgement:
    turn, quote = QUOTES[pair_id]
    values = {
        "id": pair_id,
        "answered": "answered",
        "relevance": _criterion(90),
        "accuracy": _criterion(80),
        "completeness": _criterion(70),
        "articulation": _criterion(60),
        "justification": "A solid answer.",
        "evidence_turn": turn,
        "evidence_quote": quote,
    }
    return PairJudgement(**(values | changes))


def _judge_all(batch: list[dict]) -> EvaluationAnswer:
    return EvaluationAnswer(evaluations=[_judgement(pair["id"]) for pair in batch])


def test_small_talk_and_unanswered_questions_are_not_sent_to_the_ai() -> None:
    unanswered = {**PAIRS[3], "id": "Q5", "answer_turn_ids": []}

    batches = evaluation.make_batches([*PAIRS, unanswered])

    assert [[pair["id"] for pair in batch] for batch in batches] == [["Q2", "Q3", "Q4"]]


def test_answers_go_to_the_ai_in_batches() -> None:
    many = [{**PAIRS[1], "id": f"Q{n}"} for n in range(1, 11)]

    sizes = [len(batch) for batch in evaluation.make_batches(many)]

    assert sizes == [evaluation.BATCH_SIZE, evaluation.BATCH_SIZE, 2]


def test_a_valid_answer_has_no_problems() -> None:
    batch = PAIRS[1:]

    assert evaluation.problems(_judge_all(batch), batch, TURNS_BY_ID, {}) == []


@pytest.mark.parametrize(
    ("judgements", "problem"),
    [
        ([_judgement("Q2")], "pairs_mismatch"),
        ([_judgement("Q2"), _judgement("Q3"), _judgement("Q3")], "pairs_mismatch"),
        (
            [_judgement("Q2", accuracy=None), _judgement("Q3"), _judgement("Q4")],
            "accuracy_missing",
        ),
        (
            [_judgement("Q2", evidence_turn=5), _judgement("Q3"), _judgement("Q4")],
            "evidence_turn_wrong",
        ),
        (
            [
                _judgement("Q2", evidence_quote="ten years of Kubernetes"),
                _judgement("Q3"),
                _judgement("Q4"),
            ],
            "quote_not_found",
        ),
    ],
)
def test_answers_that_fail_the_checks_are_found(
    judgements: list[PairJudgement], problem: str
) -> None:
    answer = EvaluationAnswer(evaluations=judgements)

    assert problem in evaluation.problems(answer, PAIRS[1:], TURNS_BY_ID, {})


def test_a_quote_may_differ_in_case_and_punctuation() -> None:
    answer = EvaluationAnswer(
        evaluations=[_judgement("Q2", evidence_quote="rest APIs, in fastapi")]
    )

    assert evaluation.problems(answer, [PAIRS[1]], TURNS_BY_ID, {}) == []


def test_the_score_is_the_average_of_the_criteria_that_apply() -> None:
    technical = {"relevance": {"score": 90}, "accuracy": {"score": 80}}
    behavioural = {"relevance": {"score": 90}, "accuracy": None}

    assert evaluation.answer_score(technical, "answered") == 85.0
    assert evaluation.answer_score(behavioural, "partly_answered") == 90.0
    assert evaluation.answer_score(technical, "not_answered") == 0.0


def test_behavioural_answers_are_not_judged_on_accuracy() -> None:
    pair = {**PAIRS[3], "kind": "behavioural"}

    [result] = evaluation.to_evaluations(
        EvaluationAnswer(evaluations=[_judgement("Q4")]), [pair], TURNS_BY_ID, {}
    )

    assert result["criteria"]["accuracy"] is None and result["accuracy_source"] is None
    assert result["score"] == 73.3  # (90 + 70 + 60) / 3


def test_each_evaluation_points_to_its_quote_in_the_transcript() -> None:
    [result] = evaluation.to_evaluations(
        EvaluationAnswer(evaluations=[_judgement("Q2")]), [PAIRS[1]], TURNS_BY_ID, {}
    )

    evidence = {"turn_id": 4, "start_ms": 20_000, "quote": "REST APIs in FastAPI"}
    assert result["evidence"] == evidence
    assert result["score"] == 75.0 and result["accuracy_source"] == {"type": "ai_judgement"}


def test_the_ai_never_sees_contact_details_in_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts: list[str] = []
    monkeypatch.setattr(
        evaluation.ai_client,
        "generate_structured",
        lambda prompt, schema: prompts.append(prompt) or _judge_all([PAIRS[1]]),
    )
    turns = {**TURNS_BY_ID, 4: {**TURNS_BY_ID[4], "text": "Reach me at sam@example.com"}}

    evaluation.ask_ai("Backend Engineer", [PAIRS[1]], turns, {})

    assert "sam@example.com" not in prompts[0] and "[email]" in prompts[0]


def test_a_question_without_an_answer_scores_zero() -> None:
    unanswered = {**PAIRS[3], "answer_turn_ids": []}

    [small_talk, result] = evaluation.attach([PAIRS[0], unanswered], [])

    assert small_talk["evaluation"] is None
    assert result["evaluation"]["score"] == 0.0
    assert result["evaluation"]["justification"] == evaluation.NO_ANSWER


# --- Checking accuracy against references -----------------------------------


PASSAGE = {
    "source": "fastapi_guide.pdf",
    "similarity": 0.82,
    "text": "FastAPI builds REST APIs from Python type hints.",
}


def test_a_technical_answer_records_the_reference_it_was_checked_against() -> None:
    answer = EvaluationAnswer(evaluations=[_judgement("Q2", reference_used=1)])
    found = {"Q2": [PASSAGE]}

    assert evaluation.problems(answer, [PAIRS[1]], TURNS_BY_ID, found) == []
    [result] = evaluation.to_evaluations(answer, [PAIRS[1]], TURNS_BY_ID, found)

    assert result["accuracy_source"] == {
        "type": "reference",
        "source": "fastapi_guide.pdf",
        "passage": PASSAGE["text"],
        "similarity": 0.82,
    }


def test_without_a_usable_reference_accuracy_is_the_ais_own_judgement() -> None:
    found = {"Q2": [PASSAGE]}
    answer = EvaluationAnswer(evaluations=[_judgement("Q2", reference_used=None)])

    [result] = evaluation.to_evaluations(answer, [PAIRS[1]], TURNS_BY_ID, found)

    assert result["accuracy_source"] == {"type": "ai_judgement"}


@pytest.mark.parametrize(("used", "found"), [(2, {"Q2": [PASSAGE]}), (1, {})])
def test_a_reference_that_was_not_given_is_found(used: int, found: dict) -> None:
    answer = EvaluationAnswer(evaluations=[_judgement("Q2", reference_used=used)])

    assert evaluation.problems(answer, [PAIRS[1]], TURNS_BY_ID, found) == ["reference_wrong"]


def test_the_ai_sees_the_references_of_technical_answers_only() -> None:
    behavioural = {**PAIRS[3], "kind": "behavioural"}

    text = evaluation.batch_lines(
        [PAIRS[1], behavioural], TURNS_BY_ID, {"Q2": [PASSAGE], "Q4": [PASSAGE]}
    )

    assert text.count("[R1] (from fastapi_guide.pdf)") == 1
    assert "Reference passages" not in text.split('id="Q4"')[1]


def test_a_technical_answer_without_references_says_so() -> None:
    text = evaluation.batch_lines([PAIRS[1]], TURNS_BY_ID, {"Q2": []})

    assert "Reference passages: none" in text


def test_references_are_searched_for_technical_answers_with_contacts_masked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []

    def fake_call(server: str, tool: str, arguments: dict):
        calls.append({"server": server, "tool": tool, **arguments})
        return SimpleNamespace(is_error=False, structured_content={"result": [PASSAGE]})

    monkeypatch.setattr(references.mcp_client, "call_tool", fake_call)
    turns = {**TURNS_BY_ID, 4: {**TURNS_BY_ID[4], "text": "Mail sam@example.com"}}
    behavioural = {**PAIRS[3], "kind": "behavioural"}

    found = references.for_batch([PAIRS[1], behavioural], turns)

    assert found == {"Q2": [PASSAGE]}
    [call] = calls
    assert call["server"] == "rag" and call["tool"] == "verify_answer"
    assert "sam@example.com" not in call["answer"] and "[email]" in call["answer"]


@pytest.mark.parametrize(
    "failure",
    [ConnectionError("down"), SimpleNamespace(is_error=True, structured_content=None)],
)
def test_a_knowledge_base_that_cannot_be_searched_is_reported(
    monkeypatch: pytest.MonkeyPatch, failure
) -> None:
    def fake_call(*args):
        if isinstance(failure, Exception):
            raise failure
        return failure

    monkeypatch.setattr(references.mcp_client, "call_tool", fake_call)

    with pytest.raises(references.ReferenceSearchError):
        references.for_batch([PAIRS[1]], TURNS_BY_ID)


# --- Questions about the company --------------------------------------------


POLICY = {
    "source": "company_reference_notes.txt",
    "similarity": 0.78,
    "text": "Employees may work remotely up to two days a week.",
}
COMPANY_PAIR = {**PAIRS[1], "kind": "company"}


def test_company_answers_are_checked_against_references(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    searched: list[str] = []
    monkeypatch.setattr(
        references,
        "search",
        lambda question, answer: searched.append(question) or [POLICY],
    )

    found = references.for_batch([COMPANY_PAIR], TURNS_BY_ID)

    assert found == {"Q2": [POLICY]} and searched == [COMPANY_PAIR["question"]]


def test_a_company_answer_checked_against_a_reference_is_scored_on_accuracy() -> None:
    answer = EvaluationAnswer(evaluations=[_judgement("Q2", reference_used=1)])
    found = {"Q2": [POLICY]}

    assert evaluation.problems(answer, [COMPANY_PAIR], TURNS_BY_ID, found) == []
    [result] = evaluation.to_evaluations(answer, [COMPANY_PAIR], TURNS_BY_ID, found)

    assert result["accuracy_source"]["source"] == "company_reference_notes.txt"
    assert result["criteria"]["accuracy"]["score"] == 80
    assert result["score"] == 75.0


def test_a_company_answer_without_a_reference_is_not_scored_on_accuracy() -> None:
    answer = EvaluationAnswer(evaluations=[_judgement("Q2", reference_used=None)])

    assert evaluation.problems(answer, [COMPANY_PAIR], TURNS_BY_ID, {"Q2": []}) == []
    [result] = evaluation.to_evaluations(answer, [COMPANY_PAIR], TURNS_BY_ID, {"Q2": []})

    assert result["accuracy_source"] == {"type": "not_checked"}
    # A guess from the AI is dropped, and only the other criteria count.
    assert result["criteria"]["accuracy"] is None
    assert result["score"] == 73.3  # (90 + 70 + 60) / 3


def test_a_company_answer_needs_accuracy_when_a_reference_was_used() -> None:
    answer = EvaluationAnswer(
        evaluations=[_judgement("Q2", reference_used=1, accuracy=None)]
    )

    assert evaluation.problems(answer, [COMPANY_PAIR], TURNS_BY_ID, {"Q2": [POLICY]}) == [
        "accuracy_missing"
    ]


def test_a_company_answer_without_a_reference_may_leave_accuracy_out() -> None:
    answer = EvaluationAnswer(evaluations=[_judgement("Q2", accuracy=None)])

    assert evaluation.problems(answer, [COMPANY_PAIR], TURNS_BY_ID, {"Q2": []}) == []


def test_the_ai_sees_the_references_of_company_answers() -> None:
    text = evaluation.batch_lines([COMPANY_PAIR], TURNS_BY_ID, {"Q2": [POLICY]})

    assert 'kind="company"' in text and "[R1] (from company_reference_notes.txt)" in text


def test_company_questions_are_evaluated_and_counted() -> None:
    pairs = [PAIRS[0], COMPANY_PAIR]

    assert evaluation.make_batches(pairs) == [[COMPANY_PAIR]]
    assert segmentation.counts(pairs) == {"pairs": 2, "evaluated": 1, "small_talk": 1}


# --- The graph ---------------------------------------------------------------


class FakeStore:
    def __init__(self, interview: dict | None) -> None:
        self.interview = interview
        self.saved: dict[int, list[dict]] = {}

    def load_interview(self, session_id: int) -> dict | None:
        return self.interview

    def save_analysis(
        self,
        session_id: int,
        candidate_id: int,
        pairs: list[dict],
        coverage: list[dict],
        suggestions: list[dict] | None,
    ) -> None:
        self.saved[session_id] = pairs
        self.coverage = coverage
        self.suggestions = suggestions


def _interview(status: str = SessionStatus.COMPLETED, turns: list[dict] = TURNS) -> dict:
    return {
        "candidate_id": 5,
        "status": status,
        "job_title": "Backend Engineer",
        "requirements": REQUIREMENTS,
        "cv_matches": CV_MATCHES,
        "turns": turns,
    }


def _answers(items: list):
    """Each call returns the next item; an exception is raised instead, and a
    function is called with the batch."""
    calls = iter(items)

    def ask(job_title: str, *args):
        item = next(calls)
        if isinstance(item, Exception):
            raise item
        return item(args[0]) if callable(item) else item

    return ask


def _no_references(batch: list[dict], turns: dict) -> dict:
    return {pair["id"]: [] for pair in batch if pair["kind"] == "technical"}


def _run(
    monkeypatch: pytest.MonkeyPatch,
    store: FakeStore,
    segments: list,
    judgements: list | None = None,
    find_references=_no_references,
) -> dict:
    """Run the graph once with stand-ins for the AI and the Knowledge Base.
    By default every answer is judged validly and no reference is found."""
    monkeypatch.setattr(qa, "store", store)
    monkeypatch.setattr(qa.references, "for_batch", find_references)
    monkeypatch.setattr(qa.suggestions, "in_bank", lambda question, role: False)
    monkeypatch.setattr(qa.segmentation, "ask_ai", _answers(segments))
    monkeypatch.setattr(qa.evaluation, "ask_ai", _answers(judgements or [_judge_all] * 10))
    graph = qa.build_qa_analysis_graph(InMemorySaver())
    return graph.invoke({"session_id": 9}, thread_config("test-qa"))


def test_the_evaluated_pairs_are_saved(monkeypatch: pytest.MonkeyPatch) -> None:
    store = FakeStore(_interview())

    result = _run(monkeypatch, store, [GOOD_ANSWER])

    assert not result.get("failure")
    saved = store.saved[9]
    assert [pair["id"] for pair in saved] == ["Q1", "Q2", "Q3", "Q4"]
    assert saved[0]["evaluation"] is None
    assert [pair["evaluation"]["score"] for pair in saved[1:]] == [75.0, 75.0, 75.0]


@pytest.mark.parametrize(
    ("interview", "message"),
    [
        (None, qa.NOT_FOUND),
        (_interview(status=SessionStatus.IN_PROGRESS), qa.NOT_COMPLETED),
        (_interview(turns=[]), qa.NO_TRANSCRIPT),
        (_interview(turns=TURNS[:1]), qa.NO_TRANSCRIPT),
    ],
)
def test_without_a_usable_transcript_nothing_is_analysed(
    monkeypatch: pytest.MonkeyPatch, interview: dict | None, message: str
) -> None:
    store = FakeStore(interview)

    result = _run(monkeypatch, store, [])

    assert result["failure"] == message and not store.saved


def test_an_unavailable_ai_stops_the_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    store = FakeStore(_interview())

    result = _run(monkeypatch, store, [ServiceUnavailableError("down")])

    assert result["failure"] == qa.AI_UNAVAILABLE and not store.saved


def test_an_answer_without_valid_pairs_is_asked_for_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeStore(_interview())
    empty = SegmentationAnswer(pairs=[_pair("Made up", [99], [4])])

    result = _run(monkeypatch, store, [empty, GOOD_ANSWER])

    assert result["attempts"] == 2 and len(store.saved[9]) == 4


def test_the_analysis_gives_up_after_the_last_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    store = FakeStore(_interview())
    empty = SegmentationAnswer(pairs=[])

    result = _run(monkeypatch, store, [empty] * MAX_ATTEMPTS)

    assert result["failure"] == qa.NO_PAIRS and result["attempts"] == MAX_ATTEMPTS
    assert not store.saved


def test_an_invalid_evaluation_is_asked_for_again(monkeypatch: pytest.MonkeyPatch) -> None:
    store = FakeStore(_interview())
    invalid = EvaluationAnswer(evaluations=[_judgement("Q2")])

    result = _run(monkeypatch, store, [GOOD_ANSWER], [invalid, _judge_all])

    assert not result.get("failure") and store.saved[9][3]["evaluation"]["score"] == 75.0


def test_the_interview_fails_when_an_evaluation_stays_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeStore(_interview())
    invalid = EvaluationAnswer(evaluations=[_judgement("Q2")])

    result = _run(monkeypatch, store, [GOOD_ANSWER], [invalid] * MAX_ATTEMPTS)

    assert result["failure"] == qa.INVALID_EVALUATION and not store.saved


def test_an_unavailable_ai_during_evaluation_saves_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeStore(_interview())

    result = _run(monkeypatch, store, [GOOD_ANSWER], [ServiceUnavailableError("down")])

    assert result["failure"] == qa.AI_UNAVAILABLE and not store.saved


def test_references_reach_the_ai_and_are_kept_with_the_evaluation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeStore(_interview())
    given: list[dict] = []

    def judge_with_reference(batch: list[dict]) -> EvaluationAnswer:
        return EvaluationAnswer(
            evaluations=[
                _judgement(pair["id"], reference_used=1 if pair["id"] == "Q2" else None)
                for pair in batch
            ]
        )

    def ask(job_title: str, batch: list[dict], turns: dict, found: dict):
        given.append(found)
        return judge_with_reference(batch)

    monkeypatch.setattr(qa, "store", store)
    monkeypatch.setattr(qa.suggestions, "in_bank", lambda question, role: False)
    monkeypatch.setattr(qa.segmentation, "ask_ai", _answers([GOOD_ANSWER]))
    monkeypatch.setattr(
        qa.references, "for_batch", lambda batch, turns: {"Q2": [PASSAGE], "Q3": [], "Q4": []}
    )
    monkeypatch.setattr(qa.evaluation, "ask_ai", ask)

    qa.build_qa_analysis_graph(InMemorySaver()).invoke({"session_id": 9}, thread_config("t"))

    assert given == [{"Q2": [PASSAGE], "Q3": [], "Q4": []}]
    saved = {pair["id"]: pair["evaluation"] for pair in store.saved[9]}
    assert saved["Q2"]["accuracy_source"]["source"] == "fastapi_guide.pdf"
    assert saved["Q3"]["accuracy_source"] == {"type": "ai_judgement"}


def test_behavioural_answers_need_no_reference_search(monkeypatch: pytest.MonkeyPatch) -> None:
    store = FakeStore(_interview())
    searched: list[int] = []
    behavioural = SegmentationAnswer(pairs=[_pair("A hard project", [6], [7], "behavioural")])

    def find(batch: list[dict], turns: dict) -> dict:
        searched.append(len(batch))
        return {}

    result = _run(monkeypatch, store, [behavioural], find_references=find)

    assert not result.get("failure") and searched == []


def test_company_answers_are_searched_in_the_knowledge_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeStore(_interview())
    searched: list[str] = []
    company = SegmentationAnswer(pairs=[_pair("Our remote policy", [6], [7], "company")])

    def find(batch: list[dict], turns: dict) -> dict:
        searched.extend(pair["kind"] for pair in batch)
        return {"Q1": []}

    result = _run(monkeypatch, store, [company], find_references=find)

    assert not result.get("failure") and searched == ["company"]
    evaluation_saved = store.saved[9][0]["evaluation"]
    assert evaluation_saved["accuracy_source"] == {"type": "not_checked"}


def test_the_interview_fails_when_the_knowledge_base_cannot_be_searched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeStore(_interview())

    def unreachable(batch: list[dict], turns: dict) -> dict:
        raise qa.references.ReferenceSearchError

    result = _run(monkeypatch, store, [GOOD_ANSWER], find_references=unreachable)

    assert result["failure"] == qa.NO_KNOWLEDGE_BASE and not store.saved


def test_coverage_and_suggestions_are_saved_with_the_pairs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeStore(_interview())
    tagged = SegmentationAnswer(
        pairs=[
            _pair("Greeting", [1], [2], "small_talk"),
            _pair("Python experience", [3], [4], requirements=["R1"]),
            _pair("Docker use", [3], [5], requirements=["R2"]),
            _pair("Why FastAPI", [6], [7], follow_up_of=2, requirements=["R1"]),
        ]
    )

    result = _run(monkeypatch, store, [tagged])

    assert not result.get("failure")
    statuses = {entry["requirement_id"]: entry["status"] for entry in store.coverage}
    assert statuses == {"R1": "covered", "R2": "covered", "R3": "not_explored"}
    assert [item["pair_id"] for item in store.suggestions] == ["Q2", "Q3"]


def test_the_evaluation_goes_on_when_the_question_bank_cannot_be_searched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeStore(_interview())

    def down(question: str, role: str) -> bool:
        raise qa.suggestions.QuestionBankSearchError

    monkeypatch.setattr(qa, "store", store)
    monkeypatch.setattr(qa.segmentation, "ask_ai", _answers([GOOD_ANSWER]))
    monkeypatch.setattr(qa.evaluation, "ask_ai", _answers([_judge_all]))
    monkeypatch.setattr(qa.references, "for_batch", _no_references)
    monkeypatch.setattr(qa.suggestions, "in_bank", down)

    result = qa.build_qa_analysis_graph(InMemorySaver()).invoke(
        {"session_id": 9}, thread_config("t")
    )

    assert not result.get("failure") and len(store.saved[9]) == 4
    assert store.suggestions is None


def test_with_only_small_talk_nothing_is_sent_to_the_ai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeStore(_interview())
    greeting = SegmentationAnswer(pairs=[_pair("Greeting", [1], [2], "small_talk")])

    result = _run(monkeypatch, store, [greeting], [])

    assert not result.get("failure") and store.saved[9][0]["evaluation"] is None


# --- The evaluation service --------------------------------------------------


class FakeProgress:
    task_id = "task-1"

    def __init__(self) -> None:
        self.updates: list[tuple[int, int, str | None]] = []
        self.notes: list[dict] = []

    def update(self, current: int, total: int, message: str | None = None) -> None:
        self.updates.append((current, total, message))

    def note(self, details: dict) -> None:
        self.notes.append({**details, "failures": list(details["failures"])})


class FakeGraph:
    """Streams the updates a real run would: the pairs, then one batch."""

    def __init__(self, failures: dict[int, str]) -> None:
        self.failures = failures
        self.seen: list[int] = []
        self.last: int | None = None

    def stream(self, state: dict, config: dict, stream_mode: str):
        self.seen.append(state["session_id"])
        self.last = state["session_id"]
        yield {"segment_qa": {"pairs": PAIRS, "attempts": 1}}
        yield {"evaluate_answers": {"evaluations": [{}, {}, {}]}}

    def get_state(self, config: dict):
        failure = self.failures.get(self.last)
        return SimpleNamespace(values={"failure": failure} if failure else {})


def test_one_failed_interview_does_not_stop_the_others() -> None:
    graph, progress = FakeGraph({2: qa.NO_PAIRS}), FakeProgress()

    summary = evaluation_service.run_evaluation(graph, [1, 2, 3], progress)

    assert graph.seen == [1, 2, 3]
    assert summary["total"] == 3 and summary["evaluated"] == 2 and summary["failed"] == 1
    assert summary["failures"] == [{"session_id": 2, "reason": qa.NO_PAIRS}]
    assert progress.updates[-1] == (3, 3, "Evaluated 2 of 3 interviews")


def test_the_task_keeps_which_interview_it_is_on() -> None:
    progress = FakeProgress()

    evaluation_service.run_evaluation(FakeGraph({1: qa.NO_PAIRS}), [1, 2], progress)

    assert [note["current"] for note in progress.notes] == [1, 2, None]
    assert progress.notes[1]["failures"] == [{"session_id": 1, "reason": qa.NO_PAIRS}]
    assert all(note["session_ids"] == [1, 2] for note in progress.notes)


def test_progress_follows_the_answers_of_a_single_interview() -> None:
    progress = FakeProgress()

    evaluation_service.run_evaluation(FakeGraph({}), [1], progress)

    assert (3, 3, "Interview 1 of 1 · 3 of 3 answers evaluated") in progress.updates


def test_the_task_fails_with_the_reason_when_nothing_could_be_evaluated() -> None:
    graph = FakeGraph({1: qa.AI_UNAVAILABLE})

    with pytest.raises(evaluation_service.EvaluationFailed) as error:
        evaluation_service.run_evaluation(graph, [1], FakeProgress())

    assert error.value.message == qa.AI_UNAVAILABLE


class FakeDB:
    """Answers the service's checks: whether the interview has turns, and
    whether an evaluation is running."""

    def __init__(self, has_turns: bool = True, running: bool = False) -> None:
        self.answers = [has_turns, "task-0" if running else None]

    def scalar(self, _query):
        return self.answers.pop(0)


def _session(status: str = SessionStatus.COMPLETED) -> InterviewSession:
    return InterviewSession(id=9, job_id=2, candidate_id=5, status=status)


@pytest.mark.parametrize(
    ("status", "db", "message"),
    [
        (SessionStatus.SCHEDULED, FakeDB(), evaluation_service.NOT_COMPLETED),
        (SessionStatus.COMPLETED, FakeDB(has_turns=False), evaluation_service.NO_TRANSCRIPT),
        (SessionStatus.COMPLETED, FakeDB(running=True), evaluation_service.BUSY),
    ],
)
def test_an_evaluation_starts_only_when_it_can_run(
    monkeypatch: pytest.MonkeyPatch, status: str, db: FakeDB, message: str
) -> None:
    monkeypatch.setattr(
        evaluation_service.session_service, "get_session", lambda db, sid: _session(status)
    )
    started: list[str] = []
    monkeypatch.setattr(
        evaluation_service.task_service,
        "start_task",
        lambda *args, **kwargs: started.append("task"),
    )

    with pytest.raises(ConflictError) as error:
        evaluation_service.start_evaluation(db, None, FakeGraph({}), 9, 1)

    assert error.value.message == message and not started


# --- Adding suggested questions to the question bank ------------------------


SUGGESTIONS = [
    {"pair_id": "Q2", "question": "What is a JOIN?", "kind": "technical", "added": False},
    {"pair_id": "Q3", "question": "Explain indexes", "kind": "technical", "added": True},
]


class FakeSessionDB:
    """Holds the job and records commits."""

    def __init__(self) -> None:
        self.commits = 0

    def get(self, model, key):
        return SimpleNamespace(job_code="HL-BE-01", title="Backend Engineer")

    def commit(self) -> None:
        self.commits += 1


def _suggested(monkeypatch: pytest.MonkeyPatch, suggestions_saved: list[dict] | None):
    assessment = SimpleNamespace(question_suggestions=suggestions_saved)
    added: list[dict] = []
    monkeypatch.setattr(evaluation_service, "get_assessment", lambda db, sid: assessment)
    monkeypatch.setattr(
        evaluation_service.session_service, "get_session", lambda db, sid: _session()
    )
    monkeypatch.setattr(
        evaluation_service.knowledge_service,
        "add_interview_questions",
        lambda db, code, role, questions, user: added.append(
            {"code": code, "role": role, "questions": questions}
        ),
    )
    return assessment, added


def test_ticked_questions_are_added_once_and_marked(monkeypatch: pytest.MonkeyPatch) -> None:
    assessment, added = _suggested(monkeypatch, [dict(item) for item in SUGGESTIONS])

    result = evaluation_service.add_suggested_questions(
        FakeSessionDB(), 9, ["Q2", "Q3", "Q2"], 1
    )

    assert added == [
        {"code": "HL-BE-01", "role": "Backend Engineer", "questions": ["What is a JOIN?"]}
    ]
    assert [item["added"] for item in result] == [True, True]
    assert assessment.question_suggestions == result


def test_questions_already_added_are_not_added_again(monkeypatch: pytest.MonkeyPatch) -> None:
    _, added = _suggested(monkeypatch, [dict(item) for item in SUGGESTIONS])

    evaluation_service.add_suggested_questions(FakeSessionDB(), 9, ["Q3"], 1)

    assert added == []


def test_only_suggested_questions_can_be_added(monkeypatch: pytest.MonkeyPatch) -> None:
    _, added = _suggested(monkeypatch, [dict(item) for item in SUGGESTIONS])

    with pytest.raises(AppError) as error:
        evaluation_service.add_suggested_questions(FakeSessionDB(), 9, ["Q9"], 1)

    assert error.value.message == evaluation_service.UNKNOWN_SUGGESTION and added == []


def test_nothing_can_be_added_without_suggestions(monkeypatch: pytest.MonkeyPatch) -> None:
    _suggested(monkeypatch, None)

    with pytest.raises(ConflictError) as error:
        evaluation_service.add_suggested_questions(FakeSessionDB(), 9, ["Q2"], 1)

    assert error.value.message == evaluation_service.NO_SUGGESTIONS


class FakeKnowledgeDB:
    def __init__(self, existing: Document | None) -> None:
        self.document = existing
        self.added: list = []

    def scalar(self, _query):
        return self.document

    def add(self, document: Document) -> None:
        document.id = 31
        self.document = document
        self.added.append(document)

    def flush(self) -> None:
        return None

    def commit(self) -> None:
        return None


def test_interview_questions_go_into_one_document_per_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored: list[dict] = []
    monkeypatch.setattr(
        knowledge_service.store,
        "add_chunks",
        lambda collection, document_id, chunks, metadata, first_index=0: stored.append(
            {"collection": collection, "id": document_id, "first": first_index, **metadata}
        ),
    )
    db = FakeKnowledgeDB(None)

    document = knowledge_service.add_interview_questions(
        db, "HL-BE-01", "Backend Engineer", ["What is a JOIN?", "Explain indexes"], 1
    )
    knowledge_service.add_interview_questions(
        db, "HL-BE-01", "Backend Engineer", ["What is a view?"], 1
    )

    assert len(db.added) == 1
    assert document.filename == "Interview questions - HL-BE-01.txt"
    assert document.doc_type == "questions" and document.tags == ["Backend Engineer"]
    assert document.chunk_count == 3
    assert [(item["collection"], item["first"]) for item in stored] == [
        ("question_bank", 0),
        ("question_bank", 2),
    ]
    assert stored[0]["tags"] == "Backend Engineer"


# --- Endpoints ---------------------------------------------------------------


def _auth(role: UserRole) -> dict[str, str]:
    token = create_access_token(subject="1", role=role, expires_in=timedelta(minutes=5))
    return {"Authorization": f"Bearer {token}"}


def _task() -> Task:
    return Task(
        id="task-1",
        kind=evaluation_service.TASK_KIND,
        status="pending",
        progress_current=0,
        progress_total=0,
        created_at=NOW,
    )


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(
        evaluation_service, "start_evaluation", lambda db, bg, graph, sid, uid: _task()
    )
    monkeypatch.setattr(
        evaluation_service, "start_job_evaluation", lambda db, bg, graph, jid, uid: _task()
    )
    pairs = segmentation.build_pairs(GOOD_ANSWER, TURNS)
    monkeypatch.setattr(
        evaluation_service,
        "get_assessment",
        lambda db, sid: Assessment(
            id=1,
            session_id=sid,
            candidate_id=5,
            status="analysed",
            qa_evaluations=pairs,
            coverage_map=[],
            question_suggestions=None,
            created_at=NOW,
            updated_at=NOW,
        ),
    )
    app = create_app()
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[qa.get_qa_analysis_graph] = lambda: SimpleNamespace()
    return TestClient(app)


def test_interviewer_starts_an_evaluation(client: TestClient) -> None:
    headers = _auth(UserRole.INTERVIEWER)

    one = client.post("/interviews/9/evaluate", headers=headers)
    every = client.post("/jobs/2/evaluate", headers=headers)

    assert one.status_code == every.status_code == 202
    assert one.json()["kind"] == "interview_evaluation"


def test_interviewer_adds_suggested_questions(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        evaluation_service,
        "add_suggested_questions",
        lambda db, sid, pair_ids, uid: [{**SUGGESTIONS[0], "added": True}],
    )

    response = client.post(
        "/interviews/9/assessment/questions",
        json={"pair_ids": ["Q2"]},
        headers=_auth(UserRole.INTERVIEWER),
    )
    empty = client.post(
        "/interviews/9/assessment/questions",
        json={"pair_ids": []},
        headers=_auth(UserRole.INTERVIEWER),
    )

    assert response.status_code == 200 and response.json()[0]["added"] is True
    assert empty.status_code == 422


def test_interviewer_reads_the_pairs(client: TestClient) -> None:
    response = client.get("/interviews/9/assessment", headers=_auth(UserRole.INTERVIEWER))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "analysed"
    assert body["qa_evaluations"][2]["question_turn_ids"] == [3]
    assert body["qa_evaluations"][3]["follow_up_of"] == "Q2"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/interviews/9/evaluate"),
        ("post", "/jobs/2/evaluate"),
        ("get", "/interviews/9/assessment"),
        ("post", "/interviews/9/assessment/questions"),
    ],
)
def test_candidate_cannot_evaluate_or_read_assessments(
    client: TestClient, method: str, path: str
) -> None:
    response = getattr(client, method)(path, headers=_auth(UserRole.CANDIDATE))

    assert response.status_code == 403


# --- The job's evaluation status and what the lists show ---------------------


def test_an_interview_shows_whether_it_has_been_evaluated() -> None:
    session = InterviewSession(id=9, job_id=2, candidate_id=5, status=SessionStatus.COMPLETED)

    assert session.assessment_status is None
    session.assessment = Assessment(status="analysed")
    assert session.assessment_status == "analysed"


def test_the_screening_score_comes_from_the_candidates_final_score() -> None:
    candidate = SimpleNamespace(scores={"final_score": 83.0})

    assert Assessment(candidate=None).screening_score is None
    assessment = Assessment()
    assessment.__dict__["candidate"] = candidate
    assert assessment.screening_score == 83.0


def test_an_evaluation_does_not_stop_a_fetch_or_a_screening() -> None:
    queries: list[str] = []

    class RecordingDB:
        def scalar(self, query):
            queries.append(str(query.compile(compile_kwargs={"literal_binds": True})))
            return None

    from app.services import task_service

    task_service.ensure_idle(RecordingDB(), 2, exclude=(task_service.EVALUATION,))

    assert "interview_evaluation" in queries[0] and "NOT IN" in queries[0]


def test_interviewer_reads_the_jobs_evaluation_status(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        evaluation_service,
        "evaluation_activity",
        lambda db, job_id: {"running": _task(), "last": None, "waiting": 2},
    )

    response = client.get("/jobs/2/evaluation", headers=_auth(UserRole.INTERVIEWER))
    refused = client.get("/jobs/2/evaluation", headers=_auth(UserRole.CANDIDATE))

    assert response.status_code == 200 and response.json()["waiting"] == 2
    assert refused.status_code == 403
