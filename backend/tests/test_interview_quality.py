"""Tests for interview quality (F10): the measures code works out, the check
of the AI's recommendations, the Interview Quality graph, the comparison of
a job's interviews, the service and the endpoints. No test calls the real
AI, and the database is replaced with stand-ins."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from app.core.errors import ConflictError, ServiceUnavailableError
from app.core.security import create_access_token
from app.db.session import get_db
from app.graphs.base import MAX_ATTEMPTS, thread_config
from app.graphs.interview_quality import consistency, measures, recommendations
from app.graphs.interview_quality import graph as quality
from app.graphs.interview_quality.recommendations import (
    RecommendationOut,
    RecommendationsAnswer,
)
from app.graphs.qa_analysis import store as qa_store
from app.main import create_app
from app.models import Assessment
from app.models.enums import UserRole
from app.services import evaluation_service

REAL_CHECK_QUALITY = evaluation_service.check_quality
MINUTE = 60_000


def _turn(turn_id: int, speaker: str, start_s: float, end_s: float, words: int = 20) -> dict:
    return {
        "id": turn_id,
        "speaker": speaker,
        "start_ms": int(start_s * 1000),
        "end_ms": int(end_s * 1000),
        "words": words,
    }


# The interviewer speaks 46 s, the candidate 54 s. The interviewer's turns
# 1 and 3 follow each other with no candidate turn between: one 3-minute
# stretch is made of turns 5-6.
TURNS = [
    _turn(1, "interviewer", 0, 6),
    _turn(2, "candidate", 6, 30, words=40),
    _turn(3, "interviewer", 30, 34),
    _turn(4, "candidate", 34, 36, words=3),
    _turn(5, "interviewer", 36, 50),
    _turn(6, "interviewer", 50, 58),
    _turn(7, "candidate", 58, 86, words=50),
    _turn(8, "interviewer", 86, 104),
]
TURNS_BY_ID = {turn["id"]: turn for turn in TURNS}


def _evaluation(score: float, answered: str = "answered", relevance: float = 80) -> dict:
    return {
        "answered": answered,
        "criteria": None
        if answered == "not_answered"
        else {"relevance": {"score": relevance, "reason": "r"}},
        "score": score,
    }


def _pair(pair_id, kind, question_turns, answer_turns, requirements, evaluation, start_s):
    return {
        "id": pair_id,
        "question": f"Question {pair_id}?",
        "question_turn_ids": question_turns,
        "answer_turn_ids": answer_turns,
        "start_ms": int(start_s * 1000),
        "end_ms": int(start_s * 1000) + 5000,
        "kind": kind,
        "follow_up_of": None,
        "requirement_ids": requirements,
        "evaluation": evaluation,
    }


PAIRS = [
    _pair("Q1", "small_talk", [1], [], [], None, 0),
    _pair("Q2", "technical", [1], [2], ["R1"], _evaluation(82), 0),
    _pair("Q3", "technical", [3], [4], ["R2"], _evaluation(35), 30),
    _pair("Q4", "behavioural", [5], [7], [], _evaluation(66), 36),
    _pair("Q5", "technical", [8], [], ["R2"], _evaluation(0, "not_answered"), 86),
    _pair("Q6", "company", [6], [7], [], _evaluation(72), 50),
]
PAIRS[4]["follow_up_of"] = "Q2"


def _entry(rid: str, status: str, priority: str = "must_have", average=None, ids=()) -> dict:
    return {
        "requirement_id": rid,
        "text": {"R1": "Python", "R2": "Testing", "R3": "Kubernetes", "R4": "Spark"}[rid],
        "priority": priority,
        "status": status,
        "average": average,
        "question_scores": [{"pair_id": pair_id, "score": 50} for pair_id in ids],
        "mixed": False,
        "cv": None,
    }


COVERAGE = [
    _entry("R1", "covered", average=82, ids=["Q2"]),
    _entry("R2", "weak", average=17.5, ids=["Q3", "Q5"]),
    _entry("R3", "not_explored"),
    _entry("R4", "not_explored", priority="preferred"),
]

METRICS = measures.measure(PAIRS, TURNS, planned_ms=30 * MINUTE, actual_ms=26 * MINUTE)


# --- What code measures --------------------------------------------------------


def test_speaking_time_is_shared_by_speaker() -> None:
    assert METRICS["interviewer_ms"] == 50_000
    assert METRICS["candidate_ms"] == 54_000
    assert METRICS["candidate_share"] == round(100 * 54 / 104, 1)


def test_the_longest_stretch_joins_interviewer_turns_with_no_candidate_turn_between() -> None:
    assert METRICS["longest_stretch"] == {"ms": 22_000, "start_ms": 36_000}


def test_small_talk_follow_ups_kinds_and_length_are_measured() -> None:
    assert METRICS["small_talk_questions"] == 1
    assert METRICS["small_talk_ms"] == 6_000
    assert METRICS["follow_ups"] == ["Q2"]
    assert METRICS["job_questions"] == 5
    assert (METRICS["planned_minutes"], METRICS["actual_minutes"]) == (30, 26)


def test_the_timeline_joins_a_speakers_close_turns() -> None:
    speakers = [segment["speaker"] for segment in METRICS["segments"]]

    # Turns 5 and 6 of the interviewer are one segment.
    assert speakers.count("interviewer") == 4
    assert {
        "speaker": "interviewer",
        "start_ms": 36_000,
        "end_ms": 58_000,
        "turn_id": 5,
    } in METRICS["segments"]


@pytest.mark.parametrize(
    ("pair_id", "reason"),
    [("Q3", "3-word answer"), ("Q5", "not answered")],
)
def test_questions_with_little_signal_are_found(pair_id: str, reason: str) -> None:
    part = measures.questions_part(PAIRS, TURNS_BY_ID)

    assert {"id": pair_id, "reason": reason} in part["little_signal"]


def test_an_answer_off_the_question_gives_little_signal() -> None:
    pair = _pair("Q9", "technical", [3], [2], ["R1"], _evaluation(30, relevance=20), 0)

    assert measures.little_signal_reason(pair, TURNS_BY_ID) == "answer off the question"


def test_the_questions_part_leaves_small_talk_out_and_counts_unlinked_questions() -> None:
    part = measures.questions_part(PAIRS, TURNS_BY_ID)

    # Q2 and Q6 are useful; Q3 and Q5 gave little signal; Q4 is linked to no
    # requirement. A company question needs no requirement.
    assert part["total"] == 5 and part["useful"] == 2
    assert part["not_linked"] == [{"id": "Q4"}]
    assert part["score"] == 40.0


def test_no_job_related_questions_scores_zero() -> None:
    part = measures.questions_part([PAIRS[0]], TURNS_BY_ID)

    assert part == {"score": 0.0, "useful": 0, "total": 0, "little_signal": [], "not_linked": []}


def test_coverage_counts_must_haves_double() -> None:
    part = measures.coverage_part(COVERAGE)

    # covered must-have 2 + weak must-have 1 + not explored 0 + 0, of 2+2+2+1.
    assert (part["points"], part["max"], part["score"]) == (3.0, 7, round(300 / 7, 1))
    assert part["weak"] == ["R2"] and part["missing"] == ["R3", "R4"]
    assert part["explored"] == 2 and part["total"] == 4


def test_no_requirements_leave_coverage_out() -> None:
    assert measures.coverage_part([]) is None


def _metrics(share=54, stretch_ms=180_000, small_talk=8, planned=30, actual=21) -> dict:
    return {
        "candidate_share": share,
        "longest_stretch": {"ms": stretch_ms, "start_ms": 550_000} if stretch_ms else None,
        "small_talk_share": small_talk,
        "planned_ms": planned * MINUTE if planned else None,
        "actual_ms": actual * MINUTE if actual else None,
        "planned_minutes": planned,
        "actual_minutes": actual,
    }


def test_interaction_loses_points_for_a_low_share_and_a_long_stretch() -> None:
    part = measures.interaction_part(_metrics())

    points = {item["key"]: item["points"] for item in part["penalties"]}
    assert points == {
        "speaking_share": -12.0,
        "small_talk": 0.0,
        "long_stretch": -10.0,
        "short_interview": 0.0,
    }
    assert part["score"] == 78.0


def test_interaction_penalties_have_limits() -> None:
    part = measures.interaction_part(
        _metrics(share=10, stretch_ms=600_000, small_talk=50, planned=60, actual=20)
    )

    points = {item["key"]: item["points"] for item in part["penalties"]}
    assert points == {
        "speaking_share": -40.0,
        "small_talk": -20.0,
        "long_stretch": -20.0,
        "short_interview": -20.0,
    }
    assert part["score"] == 0.0


def test_a_candidate_speaking_a_lot_is_not_penalised() -> None:
    assert measures.interaction_part(_metrics(share=85, stretch_ms=60_000))["score"] == 100.0


def test_without_speaking_time_interaction_is_left_out() -> None:
    assert measures.interaction_part(_metrics(share=None)) is None


@pytest.mark.parametrize(
    ("score", "label"),
    [(70, "good"), (69.9, "needs_improvement"), (50, "needs_improvement"), (49.9, "poor")],
)
def test_the_label_follows_the_score(score: float, label: str) -> None:
    assert measures.label(score) == label


def test_the_score_averages_the_parts_that_could_be_worked_out() -> None:
    parts = {"questions": {"score": 70}, "coverage": {"score": 55}, "interaction": None}

    assert measures.score_parts(parts) == 62.5
    assert measures.score_parts({"questions": None}) is None


def _findings(metrics=METRICS):
    parts = {
        "questions": measures.questions_part(PAIRS, TURNS_BY_ID),
        "coverage": measures.coverage_part(COVERAGE),
        "interaction": measures.interaction_part(metrics),
    }
    return measures.findings(PAIRS, COVERAGE, metrics, parts)


def test_findings_put_must_haves_first_and_point_to_their_evidence() -> None:
    found = _findings({**METRICS, "candidate_share": 50.0})

    assert [(finding["id"], finding["kind"]) for finding in found] == [
        ("F1", "not_explored"),
        ("F2", "not_explored"),
        ("F3", "weak"),
        ("F4", "little_signal"),
        ("F5", "little_signal"),
        ("F6", "not_linked"),
        ("F7", "speaking_share"),
    ]
    assert found[0]["refs"] == [
        {"type": "requirement", "id": "R3", "label": "R3 · must-have · not explored"}
    ]
    weak = found[2]
    assert [ref["id"] for ref in weak["refs"]] == ["R2", "Q3", "Q5"]
    assert "averaged 17.5 of 100" in weak["text"]
    assert found[3]["refs"][0]["label"] == "Q3 · 00:30 · 3-word answer"


def test_a_long_stretch_short_interview_and_much_small_talk_are_findings() -> None:
    metrics = {
        **METRICS,
        "candidate_share": 65,
        "longest_stretch": {"ms": 180_000, "start_ms": 550_000},
        "small_talk_share": 25.0,
        "planned_ms": 60 * MINUTE,
        "actual_ms": 20 * MINUTE,
        "planned_minutes": 60,
        "actual_minutes": 20,
    }

    kinds = [finding["kind"] for finding in _findings(metrics)]

    assert kinds[-3:] == ["long_stretch", "small_talk", "short_interview"]
    stretch = next(finding for finding in _findings(metrics) if finding["kind"] == "long_stretch")
    assert stretch["refs"][0]["label"] == "09:10 · 3:00 stretch"


def test_no_technical_question_is_a_finding() -> None:
    pairs = [PAIRS[3]]

    found = measures.findings(
        pairs, [], METRICS, {"questions": measures.questions_part(pairs, TURNS_BY_ID)}
    )

    assert found[0]["kind"] == "no_technical"


# --- The recommendations --------------------------------------------------------

FINDINGS = _findings({**METRICS, "candidate_share": 50.0})


def _rec(text: str, ids: list[str], example: str | None = None) -> RecommendationOut:
    return RecommendationOut(text=text, example_question=example, finding_ids=ids)


GOOD = RecommendationsAnswer(
    recommendations=[
        _rec("Ask about R3 Kubernetes, a must-have no question explored.", ["F1"], "How?"),
        _rec("Let the candidate talk more than you do.", ["F7"], "Why?"),
    ]
)


def test_proven_recommendations_get_the_chips_of_their_findings() -> None:
    accepted, problems = recommendations.check_answer(GOOD, FINDINGS)

    assert not problems
    assert [item["id"] for item in accepted] == ["M1", "M2"]
    assert accepted[0]["refs"] == FINDINGS[0]["refs"]
    assert accepted[0]["example_question"] == "How?"
    # An example question only goes with a requirement to explore.
    assert accepted[1]["example_question"] is None


@pytest.mark.parametrize(
    ("item", "problem"),
    [
        (_rec("Ask about R3.", ["F99"]), "unknown_finding"),
        (_rec("Ask about R3.", []), "finding_missing"),
        (_rec("Ask about R4 too.", ["F1"]), "id_not_in_findings"),
        (_rec("They spoke 35% of the time.", ["F7"]), "number_not_in_findings"),
        (_rec("  ", ["F1"]), "text_missing"),
    ],
)
def test_recommendations_that_cannot_be_proven_are_problems(
    item: RecommendationOut, problem: str
) -> None:
    accepted, problems = recommendations.check_answer(
        RecommendationsAnswer(recommendations=[item]), FINDINGS
    )

    assert accepted == [] and problem in problems


def test_the_ai_never_sees_contact_details() -> None:
    finding = {**FINDINGS[3], "text": 'Q3 ("Mail me at a@b.com?") gave little signal.'}

    assert "a@b.com" not in recommendations.fact_lines([finding])


# --- The graph -------------------------------------------------------------------


class FakeStore:
    def __init__(self, loaded: dict | None = None) -> None:
        self.loaded = loaded
        self.saved: list[dict] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(quality.store, "load_interview", lambda session_id: self.loaded)
        monkeypatch.setattr(
            quality.store, "save_quality", lambda session_id, value: self.saved.append(value)
        )


LOADED = {
    "job_title": "Backend Engineer",
    "pairs": PAIRS,
    "coverage": COVERAGE,
    "turns": TURNS,
    "planned_ms": 30 * MINUTE,
    "actual_ms": 26 * MINUTE,
}


class FakeAI:
    def __init__(self, answers: list) -> None:
        self.answers = answers
        self.calls: list[list[str] | None] = []

    def __call__(self, job_title, findings, problems=None):
        self.calls.append(problems)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def _run(monkeypatch, answers: list, loaded=LOADED):
    store = FakeStore(loaded)
    store.install(monkeypatch)
    ai = FakeAI(answers)
    monkeypatch.setattr(quality.recommendations, "ask_ai", ai)
    graph = quality.build_interview_quality_graph(InMemorySaver())
    config = thread_config("interview-quality-9")
    graph.invoke({"session_id": 9}, config)
    return graph.get_state(config).values, store, ai


def test_the_quality_is_measured_scored_and_saved_with_recommendations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values, store, ai = _run(monkeypatch, [GOOD])

    saved = store.saved[0]
    assert saved["status"] == "checked"
    assert saved["parts"]["questions"]["score"] == 40.0
    assert saved["score"] == measures.score_parts(saved["parts"])
    assert saved["label"] == measures.label(saved["score"])
    assert saved["recommendations"]["status"] == "written"
    assert [item["id"] for item in saved["recommendations"]["items"]] == ["M1", "M2"]
    assert saved["explored"] == ["R1", "R2"]
    assert saved["requirements"][0] == {"id": "R1", "text": "Python", "priority": "must_have"}
    assert ai.calls == [[]]


def test_the_saved_result_holds_no_transcript_text(monkeypatch: pytest.MonkeyPatch) -> None:
    _, store, _ = _run(monkeypatch, [GOOD])

    assert "text" not in store.saved[0]["metrics"]["segments"][0]


def test_unproven_recommendations_are_asked_for_again(monkeypatch: pytest.MonkeyPatch) -> None:
    bad = RecommendationsAnswer(recommendations=[_rec("Ask about R4.", ["F1"])])

    _, store, ai = _run(monkeypatch, [bad, GOOD])

    assert ai.calls == [[], ["id_not_in_findings"]]
    assert len(store.saved[0]["recommendations"]["items"]) == 2


def test_recommendations_still_unproven_after_the_last_attempt_are_left_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mixed = RecommendationsAnswer(
        recommendations=[GOOD.recommendations[0], _rec("Ask about R4.", ["F1"])]
    )

    _, store, ai = _run(monkeypatch, [mixed] * MAX_ATTEMPTS)

    assert len(ai.calls) == MAX_ATTEMPTS
    items = store.saved[0]["recommendations"]["items"]
    assert [item["text"] for item in items] == [GOOD.recommendations[0].text]


def test_an_unavailable_ai_still_saves_what_code_measured(monkeypatch: pytest.MonkeyPatch) -> None:
    values, store, _ = _run(monkeypatch, [ServiceUnavailableError("down")])

    saved = store.saved[0]
    assert saved["score"] is not None and saved["findings"]
    assert saved["recommendations"] == {
        "status": "not_written",
        "reason": "ai_unavailable",
        "items": [],
    }
    assert values["ai_failed"]


def test_nothing_to_improve_needs_no_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    pairs = [PAIRS[1]]
    loaded = {
        **LOADED,
        "pairs": pairs,
        "coverage": [COVERAGE[0]],
        "turns": [_turn(1, "interviewer", 0, 30), _turn(2, "candidate", 30, 95, words=60)],
        "actual_ms": 25 * MINUTE,
    }

    _, store, ai = _run(monkeypatch, [], loaded=loaded)

    assert ai.calls == []
    assert store.saved[0]["recommendations"]["status"] == "none_needed"
    assert store.saved[0]["label"] == "good"


def test_an_interview_not_analysed_is_not_checked(monkeypatch: pytest.MonkeyPatch) -> None:
    values, store, _ = _run(monkeypatch, [], loaded=None)

    assert values["failure"] == quality.NOT_ANALYSED and store.saved == []


def test_a_new_evaluation_clears_the_old_quality() -> None:
    assert "interview_quality" in qa_store.LATER_FIELDS


# --- Consistency across the job's interviews ------------------------------------

REQUIREMENTS = [
    {"id": "R1", "text": "Python", "priority": "must_have"},
    {"id": "R3", "text": "Kubernetes", "priority": "must_have"},
    {"id": "R4", "text": "Spark", "priority": "preferred"},
]


def _row(session_id, name, minutes=26, questions=11, share=63.0, explored=("R1", "R3")):
    return {
        "session_id": session_id,
        "candidate_name": name,
        "interview_at": None,
        "minutes": minutes,
        "questions": questions,
        "candidate_share": share,
        "explored": list(explored),
        "requirements": REQUIREMENTS,
        "quality_score": 70.0,
        "quality_label": "good",
    }


ROWS = [
    _row(1, "Tanvir"),
    _row(2, "Ayesha", minutes=28, questions=12, share=66.0),
    _row(3, "Sabbir", minutes=21, questions=10, share=54.0, explored=("R1",)),
    _row(4, "Karim", minutes=11, questions=4, share=61.0),
    _row(5, "Nadia", minutes=27, share=38.0, explored=("R1", "R3", "R4")),
]


def test_fewer_than_two_interviews_are_not_compared() -> None:
    result = consistency.job_consistency([ROWS[0]])

    assert result == {
        "count": 1,
        "min_interviews": 2,
        "typical": None,
        "requirements": [],
        "interviews": [],
        "differ": 0,
    }


def test_the_typical_interview_is_the_middle_value() -> None:
    result = consistency.job_consistency(ROWS)

    assert result["typical"] == {"minutes": 26, "questions": 11, "candidate_share": 61.0}


def test_each_requirement_shows_how_many_interviews_asked_it() -> None:
    result = consistency.job_consistency(ROWS)

    assert [
        (item["id"], item["asked"], item["mostly_missed"]) for item in result["requirements"]
    ] == [
        ("R1", 5, False),
        ("R3", 4, False),
        ("R4", 1, True),
    ]


def test_interviews_that_differ_are_flagged_most_differences_first() -> None:
    result = consistency.job_consistency(ROWS)

    by_name = {item["candidate_name"]: item for item in result["interviews"]}
    assert [flag["kind"] for flag in by_name["Karim"]["flags"]] == ["length", "questions"]
    assert by_name["Karim"]["flags"][0]["text"] == "11 min · typical 26 min"
    sabbir = by_name["Sabbir"]["flags"]
    assert sabbir == [
        {
            "kind": "must_have_not_asked",
            "requirement_id": "R3",
            "text": "R3 Kubernetes not asked · asked in 4 of 4 others",
            "asked": 4,
            "others": 4,
        }
    ]
    assert by_name["Nadia"]["flags"][0]["kind"] == "speaking_share"
    assert by_name["Tanvir"]["flags"] == []
    # A preferred requirement not asked is never flagged.
    assert all(flag["kind"] != "must_have_not_asked" for flag in by_name["Tanvir"]["flags"])
    assert result["interviews"][0]["candidate_name"] == "Karim"
    assert result["differ"] == 3
    assert "requirements" not in result["interviews"][0]


def test_a_must_have_missed_in_most_interviews_is_not_flagged_for_one() -> None:
    rows = [_row(1, "A", explored=("R1",)), _row(2, "B", explored=("R1",)), _row(3, "C")]

    result = consistency.job_consistency(rows)

    assert all(not item["flags"] for item in result["interviews"])


# --- The service -------------------------------------------------------------------


def _assessment(status: str = "approved", quality_value: dict | None = None) -> Assessment:
    return Assessment(status=status, interview_quality=quality_value)


@pytest.mark.parametrize(
    ("assessment", "message"),
    [
        (_assessment("analysed"), evaluation_service.NO_REPORT),
        (
            _assessment(quality_value={"recommendations": {"status": "written"}}),
            evaluation_service.QUALITY_CHECKED,
        ),
    ],
)
def test_the_quality_is_checked_only_when_needed(
    monkeypatch: pytest.MonkeyPatch, assessment: Assessment, message: str
) -> None:
    monkeypatch.setattr(
        evaluation_service.session_service, "get_session", lambda db, sid: SimpleNamespace(job_id=1)
    )
    monkeypatch.setattr(evaluation_service, "get_assessment", lambda db, sid: assessment)

    with pytest.raises(ConflictError) as error:
        evaluation_service.start_quality_check(None, None, 9, 1)

    assert error.value.message == message


def test_unwritten_recommendations_can_be_checked_again(monkeypatch: pytest.MonkeyPatch) -> None:
    assessment = _assessment(quality_value={"recommendations": {"status": "not_written"}})
    monkeypatch.setattr(
        evaluation_service.session_service, "get_session", lambda db, sid: SimpleNamespace(job_id=1)
    )
    monkeypatch.setattr(evaluation_service, "get_assessment", lambda db, sid: assessment)
    monkeypatch.setattr(evaluation_service, "ensure_no_evaluation", lambda db: None)
    started = []
    monkeypatch.setattr(
        evaluation_service.task_service,
        "start_task",
        lambda *args, **kwargs: started.append(kwargs) or "task",
    )

    assert evaluation_service.start_quality_check(None, None, 9, 1) == "task"
    assert started == [{"job_id": 1}]


def _progress():
    progress = SimpleNamespace(task_id="t", updates=[], notes=[])
    progress.update = lambda current, total, message=None: progress.updates.append(message)
    progress.note = lambda details: progress.notes.append(details)
    return progress


def test_the_quality_only_run_is_marked_for_the_screens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evaluation_service, "check_quality", lambda session_id: {})
    progress = _progress()

    summary = evaluation_service.run_quality_check(9, progress)

    assert summary["quality_only"] and progress.notes[0]["quality_only"]
    assert "Interview 1 of 1 · checking interview quality" in progress.updates


def test_a_quality_check_the_ai_could_not_do_fails_with_the_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(evaluation_service, "check_quality", lambda session_id: {"ai_failed": True})
    progress = _progress()

    with pytest.raises(evaluation_service.EvaluationFailed) as error:
        evaluation_service.run_quality_check(9, progress)

    assert error.value.message == evaluation_service.QUALITY_NOT_WRITTEN
    assert progress.notes[-1]["failures"][0]["session_id"] == 9


class FakeQualityGraph:
    checkpointer = None

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.runs: list[tuple[dict, dict]] = []

    def invoke(self, state, config):
        if self.fail:
            raise RuntimeError("broken")
        self.runs.append((state, config))

    def get_state(self, config):
        return SimpleNamespace(values={"score": 70})


def test_the_quality_check_runs_on_its_own_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = FakeQualityGraph()
    monkeypatch.setattr(evaluation_service, "check_quality", REAL_CHECK_QUALITY)
    monkeypatch.setattr(
        evaluation_service.quality_graph, "get_interview_quality_graph", lambda: graph
    )

    assert evaluation_service.check_quality(9) == {"score": 70}
    assert graph.runs == [({"session_id": 9}, thread_config("interview-quality-9"))]


def test_a_broken_quality_check_never_stops_the_evaluation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(evaluation_service, "check_quality", REAL_CHECK_QUALITY)
    monkeypatch.setattr(
        evaluation_service.quality_graph,
        "get_interview_quality_graph",
        lambda: FakeQualityGraph(fail=True),
    )

    assert evaluation_service.check_quality(9) == {"failure": evaluation_service.QUALITY_FAILED}


@pytest.mark.parametrize(("failure", "checked"), [(None, [9]), ("No report", [])])
def test_the_quality_is_checked_after_a_written_report(
    monkeypatch: pytest.MonkeyPatch, failure, checked
) -> None:
    calls: list[int] = []
    monkeypatch.setattr(
        evaluation_service, "check_quality", lambda session_id: calls.append(session_id)
    )
    monkeypatch.setattr(
        evaluation_service,
        "write_report",
        lambda graph, session_id, show=None: {"failure": failure} if failure else {},
    )
    progress = _progress()

    if failure:
        with pytest.raises(evaluation_service.EvaluationFailed):
            evaluation_service.run_report(None, 9, progress)
    else:
        evaluation_service.run_report(None, 9, progress)

    assert calls == checked
    if not failure:
        assert "Interview 1 of 1 · checking interview quality" in progress.updates


# --- The endpoints -----------------------------------------------------------------


def _auth(role: UserRole) -> dict[str, str]:
    token = create_access_token(subject="1", role=role, expires_in=timedelta(minutes=5))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: None
    return TestClient(app)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/interviews/9/assessment/quality"),
        ("get", "/jobs/1/interview-consistency"),
    ],
)
def test_candidate_cannot_reach_interview_quality(
    client: TestClient, method: str, path: str
) -> None:
    response = getattr(client, method)(path, headers=_auth(UserRole.CANDIDATE))

    assert response.status_code == 403


def test_the_consistency_is_returned_to_the_interviewer(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        evaluation_service,
        "interview_consistency",
        lambda db, job_id: consistency.job_consistency(ROWS),
    )

    response = client.get("/jobs/1/interview-consistency", headers=_auth(UserRole.INTERVIEWER))

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 5 and body["differ"] == 3
    assert body["interviews"][0]["candidate_name"] == "Karim"


def test_numbers_in_a_recommendation_must_be_in_its_findings() -> None:
    item = _rec("They spoke 50% of the time; aim for 60-70%.", ["F7"])

    accepted, problems = recommendations.check_answer(
        RecommendationsAnswer(recommendations=[item]), FINDINGS
    )

    assert not problems and accepted[0]["text"].startswith("They spoke 50%")
