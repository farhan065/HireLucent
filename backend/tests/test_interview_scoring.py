"""Tests for the interview performance score (F9): the problem-solving and
depth judgements in LangGraph 3, the six dimensions and the score made from
them in LangGraph 4, and section D of the report PDF. No test calls the real
AI, and the database is replaced with stand-ins."""

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.graphs.base import MAX_ATTEMPTS
from app.graphs.final_assessment import dimensions
from app.graphs.final_assessment import graph as final
from app.graphs.final_assessment import store as final_store
from app.graphs.qa_analysis import evaluation
from app.graphs.qa_analysis import store as qa_store
from app.graphs.qa_analysis.evaluation import EvaluationAnswer, ShownCriterion
from app.schemas.assessment import AnswerEvaluation, InterviewDimensions
from app.services import report_pdf
from tests.test_final_assessment import CONFIG, GOOD_REPORT, FakeAI, FakeStore
from tests.test_qa_analysis import PAIRS as QA_PAIRS
from tests.test_qa_analysis import TURNS_BY_ID, _judgement
from tests.test_report_pdf import _context

# --- LangGraph 3: problem-solving and depth per answer ----------------------


def _shown(score: int, quote: str) -> ShownCriterion:
    return ShownCriterion(score=score, reason="Reasoned it through.", quote=quote)


def test_problem_solving_and_depth_are_kept_with_the_transcripts_words() -> None:
    batch = QA_PAIRS[1:2]
    answer = EvaluationAnswer(
        evaluations=[_judgement("Q2", problem_solving=_shown(78, "REST APIs in FastAPI"))]
    )

    assert evaluation.problems(answer, batch, TURNS_BY_ID, {}) == []
    [result] = evaluation.to_evaluations(answer, batch, TURNS_BY_ID, {})
    assert result["problem_solving"]["score"] == 78
    assert result["problem_solving"]["evidence"]["quote"] == "REST APIs in FastAPI"
    assert result["depth"] is None


def test_the_new_criteria_never_change_the_answers_own_score() -> None:
    batch = QA_PAIRS[1:2]
    plain = EvaluationAnswer(evaluations=[_judgement("Q2")])
    with_skills = EvaluationAnswer(
        evaluations=[
            _judgement(
                "Q2",
                problem_solving=_shown(10, "REST APIs in FastAPI"),
                depth=_shown(5, "REST APIs in FastAPI"),
            )
        ]
    )

    [before] = evaluation.to_evaluations(plain, batch, TURNS_BY_ID, {})
    [after] = evaluation.to_evaluations(with_skills, batch, TURNS_BY_ID, {})
    assert before["score"] == after["score"]
    assert before["score"] == evaluation.answer_score(before["criteria"], "answered")


def test_a_problem_solving_quote_not_in_the_answer_is_a_problem_then_dropped() -> None:
    batch = QA_PAIRS[1:2]
    answer = EvaluationAnswer(
        evaluations=[_judgement("Q2", depth=_shown(90, "led a team of twelve engineers"))]
    )

    assert evaluation.problems(answer, batch, TURNS_BY_ID, {}) == ["depth_quote_not_found"]
    # After the last attempt it is left out rather than counted without evidence.
    [result] = evaluation.to_evaluations(answer, batch, TURNS_BY_ID, {})
    assert result["depth"] is None


def test_a_question_not_answered_has_no_problem_solving_or_depth() -> None:
    batch = QA_PAIRS[1:2]
    answer = EvaluationAnswer(
        evaluations=[
            _judgement(
                "Q2",
                answered="not_answered",
                problem_solving=_shown(60, "anything at all"),
            )
        ]
    )

    assert evaluation.problems(answer, batch, TURNS_BY_ID, {}) == []
    [result] = evaluation.to_evaluations(answer, batch, TURNS_BY_ID, {})
    assert result["problem_solving"] is None and result["depth"] is None
    assert evaluation.no_answer(QA_PAIRS[1])["problem_solving"] is None


def test_the_prompt_asks_for_problem_solving_and_depth_only_when_shown() -> None:
    assert "problem_solving: only when the answer shows" in evaluation.PROMPT
    assert "depth: only when the answer describes the candidate's own" in evaluation.PROMPT
    assert "never about fluency" in evaluation.PROMPT


def test_the_saved_evaluation_matches_the_api_schema() -> None:
    answer = EvaluationAnswer(
        evaluations=[_judgement("Q2", problem_solving=_shown(78, "REST APIs in FastAPI"))]
    )
    [result] = evaluation.to_evaluations(answer, QA_PAIRS[1:2], TURNS_BY_ID, {})

    shown = AnswerEvaluation.model_validate(result).problem_solving
    assert shown is not None and shown.evidence.quote == "REST APIs in FastAPI"


# --- The six dimensions -----------------------------------------------------


def _crit(score: int) -> dict:
    return {"score": score, "reason": f"Reason {score}."}


def _pair(pid: str, kind: str, evaluation_: dict | None, start_ms: int = 0) -> dict:
    return {
        "id": pid,
        "question": f"Question {pid}",
        "kind": kind,
        "question_turn_ids": [1],
        "answer_turn_ids": [7] if evaluation_ else [],
        "start_ms": start_ms,
        "end_ms": start_ms + 9000,
        "follow_up_of": None,
        "requirement_ids": [],
        "evaluation": evaluation_,
    }


def _eval(
    relevance: int,
    completeness: int,
    articulation: int,
    accuracy: int | None = None,
    problem_solving: int | None = None,
    depth: int | None = None,
) -> dict:
    def shown(score):
        if score is None:
            return None
        evidence = {"turn_id": 7, "start_ms": 60000, "quote": "my own words"}
        return {"score": score, "reason": "Shown.", "evidence": evidence}

    return {
        "answered": "answered",
        "criteria": {
            "relevance": _crit(relevance),
            "accuracy": _crit(accuracy) if accuracy is not None else None,
            "completeness": _crit(completeness),
            "articulation": _crit(articulation),
        },
        "score": 0.0,
        "justification": "A reason.",
        "evidence": {"turn_id": 7, "start_ms": 60000, "quote": "my own words"},
        "accuracy_source": None,
        "problem_solving": shown(problem_solving),
        "depth": shown(depth),
    }


NOT_ANSWERED = {
    "answered": "not_answered",
    "criteria": None,
    "score": 0.0,
    "justification": "No answer given.",
    "evidence": None,
    "accuracy_source": None,
    "problem_solving": None,
    "depth": None,
}

# The worked example from the F9 explanation (small talk, a definition, a
# problem to solve, real experience, a follow-up, a shallow answer, a
# company question, a question not answered and a partly wrong answer).
DEMO = [
    _pair("Q1", "small_talk", None),
    _pair("Q2", "technical", _eval(85, 70, 75, accuracy=80)),
    _pair("Q3", "technical", _eval(90, 80, 80, accuracy=85, problem_solving=85)),
    _pair("Q4", "technical", _eval(85, 75, 70, accuracy=80, depth=80)),
    _pair("Q5", "behavioural", _eval(80, 75, 70, problem_solving=75, depth=85)),
    _pair("Q6", "behavioural", _eval(70, 50, 60, problem_solving=60)),
    _pair("Q7", "behavioural", _eval(60, 40, 55, depth=30)),
    _pair("Q8", "company", _eval(75, 65, 80)),
    _pair("Q9", "technical", dict(NOT_ANSWERED)),
    _pair("Q10", "technical", _eval(70, 45, 65, accuracy=40)),
]


def _cov(rid: str, priority: str, status: str, average: float | None) -> dict:
    return {
        "requirement_id": rid,
        "text": f"Requirement {rid}",
        "priority": priority,
        "status": status,
        "average": average,
        "question_scores": [],
        "mixed": False,
        "cv": None,
    }


DEMO_COVERAGE = [
    _cov("R1", "must_have", "covered", 70.8),
    _cov("R2", "must_have", "covered", 72.1),
    _cov("R3", "must_have", "covered", 83.8),
    _cov("R4", "preferred", "weak", 0.0),
    _cov("R5", "preferred", "weak", 51.7),
    _cov("R6", "preferred", "not_explored", None),
]


def _by_key(scored: dict) -> dict:
    return {item["key"]: item for item in scored["dimensions"]}


def test_each_dimension_averages_what_langgraph_3_judged() -> None:
    scored = dimensions.dimensions(DEMO, DEMO_COVERAGE)
    items = _by_key(scored)

    # Technical: each technical answer's accuracy and completeness, Q9 = 0.
    assert items["technical"]["score"] == round((75 + 82.5 + 77.5 + 0 + 42.5) / 5, 1)
    # Communication leaves the unanswered Q9 out.
    assert items["communication"]["score"] == round(555 / 8, 1)
    assert "Q9" not in [a["pair_id"] for a in items["communication"]["answers"]]
    # Relevance counts the unanswered Q9 as 0.
    assert items["relevance"]["score"] == round(615 / 9, 1)
    assert items["problem_solving"]["score"] == round((85 + 75 + 60) / 3, 1)
    assert items["depth"]["score"] == round((80 + 85 + 30) / 3, 1)
    assert [a["pair_id"] for a in items["problem_solving"]["answers"]] == ["Q3", "Q5", "Q6"]


def test_alignment_weights_must_haves_double_and_leaves_unexplored_out() -> None:
    items = _by_key(dimensions.dimensions(DEMO, DEMO_COVERAGE))

    expected = (70.8 * 2 + 72.1 * 2 + 83.8 * 2 + 0 + 51.7) / 8
    assert items["alignment"]["score"] == round(expected, 1)
    assert items["alignment"]["not_explored"] == ["R6"]
    assert [r["requirement_id"] for r in items["alignment"]["requirements"]] == [
        "R1",
        "R2",
        "R3",
        "R4",
        "R5",
    ]


def test_the_interview_score_averages_the_six_dimensions_equally() -> None:
    scored = dimensions.dimensions(DEMO, DEMO_COVERAGE)

    scores = [item["score"] for item in scored["dimensions"]]
    assert scored["status"] == dimensions.SCORED and scored["assessed"] == 6
    assert scored["score"] == round(sum(scores) / 6, 1)
    assert dimensions.interview_score(DEMO, scored) == scored["score"]


def test_a_dimension_with_nothing_to_judge_is_not_assessed_not_zero() -> None:
    without_problems = [
        {**pair, "evaluation": {**pair["evaluation"], "problem_solving": None}}
        if pair["evaluation"]
        else pair
        for pair in DEMO
    ]

    scored = dimensions.dimensions(without_problems, DEMO_COVERAGE)
    item = _by_key(scored)["problem_solving"]

    assert item["score"] is None and item["answers"] == []
    assert item["based_on"] == "No answer showed problem-solving."
    others = [i["score"] for i in scored["dimensions"] if i["score"] is not None]
    assert scored["assessed"] == 5 and scored["score"] == round(sum(others) / 5, 1)


def test_fewer_than_three_dimensions_give_no_interview_score() -> None:
    behavioural_only = [_pair("Q1", "behavioural", _eval(70, 60, 66))]

    scored = dimensions.dimensions(behavioural_only, [])

    # Communication and relevance only: technical, problem-solving, depth and
    # alignment have nothing to judge.
    assert scored["assessed"] == 2 and scored["status"] == dimensions.NOT_ENOUGH
    assert scored["score"] is None


def test_an_interview_without_job_related_questions_has_no_score() -> None:
    scored = dimensions.dimensions([_pair("Q1", "small_talk", None)], DEMO_COVERAGE[5:])

    assert scored["assessed"] == 0 and scored["score"] is None


def test_an_interview_evaluated_before_f9_keeps_the_answer_average() -> None:
    old = [
        _pair("Q2", "technical", {**NOT_ANSWERED, "answered": "answered", "score": 80.0}),
        _pair("Q3", "behavioural", {**NOT_ANSWERED, "answered": "answered", "score": 60.0}),
    ]
    for pair in old:
        del pair["evaluation"]["problem_solving"], pair["evaluation"]["depth"]

    assert dimensions.dimensions(old, DEMO_COVERAGE) is None
    assert dimensions.interview_score(old, None) == 70.0


def test_the_dimensions_match_the_api_schema() -> None:
    scored = dimensions.dimensions(DEMO, DEMO_COVERAGE)

    parsed = InterviewDimensions.model_validate(scored)
    assert [item.key for item in parsed.dimensions] == list(dimensions.ORDER)


# --- LangGraph 4 ------------------------------------------------------------


def test_the_report_uses_the_interview_score_from_the_dimensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeStore()
    store.results = {**store.results, "pairs": DEMO, "coverage": DEMO_COVERAGE}
    store.install(monkeypatch)
    # The report's quotes belong to another transcript, so they are untraced
    # and asked for again; the scores do not depend on the report.
    monkeypatch.setattr(final.report, "ask_ai", FakeAI([GOOD_REPORT] * MAX_ATTEMPTS))
    monkeypatch.setattr(final.cv_claims, "extract_claims", lambda cv: [])

    graph = final.build_final_assessment_graph(InMemorySaver())
    graph.invoke({"session_id": 9}, CONFIG)

    draft = store.drafts[0]
    expected = dimensions.dimensions(DEMO, DEMO_COVERAGE)
    assert draft["interview_dimensions"] == expected
    assert draft["interview_score"] == expected["score"]
    assert draft["overall_score"] == round(0.4 * 80 + 0.6 * expected["score"], 1)


def test_score_dimensions_runs_before_compute_scores() -> None:
    graph = final.build_final_assessment_graph(InMemorySaver())
    edges = {(edge.source, edge.target) for edge in graph.get_graph().edges}

    assert ("score_dimensions", "compute_scores") in edges
    assert ("load_results", "score_dimensions") in edges


def test_the_dimensions_are_saved_and_cleared_with_the_report() -> None:
    assert "interview_dimensions" in final_store.DRAFT_FIELDS
    assert "interview_dimensions" in qa_store.LATER_FIELDS


# --- Report PDF section D ---------------------------------------------------


def test_the_pdf_lists_the_six_dimensions() -> None:
    scored = dimensions.dimensions(DEMO, DEMO_COVERAGE)

    html = report_pdf.dimensions_html(_context(interview_dimensions=scored))

    assert "D · Interview performance" in html
    for name in dimensions.NAMES.values():
        assert name in html
    assert "6 of 6" in html and "R6 not explored" in html


def test_the_pdf_marks_a_dimension_not_assessed() -> None:
    scored = dimensions.dimensions([_pair("Q1", "behavioural", _eval(70, 60, 66))], [])

    html = report_pdf.dimensions_html(_context(interview_dimensions=scored))

    assert "Not assessed" in html and "there is no interview score" in html


def test_the_pdf_explains_an_interview_evaluated_before_f9() -> None:
    html = report_pdf.dimensions_html(_context(interview_dimensions=None))

    assert "evaluated before the interview performance dimensions existed" in html


def test_the_whole_pdf_builds_with_section_d() -> None:
    scored = dimensions.dimensions(DEMO, DEMO_COVERAGE)

    pdf = report_pdf.build_pdf(_context(interview_dimensions=scored))

    assert pdf.startswith(b"%PDF")
