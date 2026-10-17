"""Tests for the Q&A Analysis graph (question-answer segmentation), the
evaluation service and its endpoints. No test calls the real AI, and the
database is replaced with stand-ins."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from app.core.errors import ConflictError, ServiceUnavailableError
from app.core.security import create_access_token
from app.db.session import get_db
from app.graphs.base import MAX_ATTEMPTS, thread_config
from app.graphs.qa_analysis import graph as qa
from app.graphs.qa_analysis import segmentation
from app.graphs.qa_analysis.segmentation import PairOut, SegmentationAnswer
from app.main import create_app
from app.models import Assessment, InterviewSession, Task
from app.models.enums import SessionStatus, UserRole
from app.services import evaluation_service

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


# --- The graph ---------------------------------------------------------------


class FakeStore:
    def __init__(self, interview: dict | None) -> None:
        self.interview = interview
        self.saved: dict[int, list[dict]] = {}

    def load_interview(self, session_id: int) -> dict | None:
        return self.interview

    def save_analysis(self, session_id: int, candidate_id: int, pairs: list[dict]) -> None:
        self.saved[session_id] = pairs


def _interview(status: str = SessionStatus.COMPLETED, turns: list[dict] = TURNS) -> dict:
    return {
        "candidate_id": 5,
        "status": status,
        "job_title": "Backend Engineer",
        "turns": turns,
    }


def _run(monkeypatch: pytest.MonkeyPatch, store: FakeStore, answers: list) -> dict:
    """Run the graph once. Each AI call returns the next answer in the list;
    an exception in the list is raised instead."""
    calls = iter(answers)

    def fake_ask(job_title: str, turns: list[dict]):
        answer = next(calls)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(qa, "store", store)
    monkeypatch.setattr(qa.segmentation, "ask_ai", fake_ask)
    graph = qa.build_qa_analysis_graph(InMemorySaver())
    return graph.invoke({"session_id": 9}, thread_config("test-qa"))


def test_the_pairs_are_saved(monkeypatch: pytest.MonkeyPatch) -> None:
    store = FakeStore(_interview())

    result = _run(monkeypatch, store, [GOOD_ANSWER])

    assert not result.get("failure")
    assert [pair["id"] for pair in store.saved[9]] == ["Q1", "Q2", "Q3", "Q4"]


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


# --- The evaluation service --------------------------------------------------


class FakeProgress:
    task_id = "task-1"

    def __init__(self) -> None:
        self.updates: list[tuple[int, int, str | None]] = []

    def update(self, current: int, total: int, message: str | None = None) -> None:
        self.updates.append((current, total, message))


class FakeGraph:
    def __init__(self, failures: dict[int, str]) -> None:
        self.failures = failures
        self.seen: list[int] = []

    def invoke(self, state: dict, config: dict) -> dict:
        self.seen.append(state["session_id"])
        failure = self.failures.get(state["session_id"])
        return {"failure": failure} if failure else {}


def test_one_failed_interview_does_not_stop_the_others() -> None:
    graph, progress = FakeGraph({2: qa.NO_PAIRS}), FakeProgress()

    summary = evaluation_service.run_evaluation(graph, [1, 2, 3], progress)

    assert graph.seen == [1, 2, 3]
    assert summary == {"total": 3, "evaluated": 2, "failed": 1}
    assert progress.updates[-1] == (3, 3, "Evaluated 2 of 3 interviews")


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
    ],
)
def test_candidate_cannot_evaluate_or_read_assessments(
    client: TestClient, method: str, path: str
) -> None:
    response = getattr(client, method)(path, headers=_auth(UserRole.CANDIDATE))

    assert response.status_code == 403
