"""Tests for the AI help in the interview room: suggested questions, the
read-only chat with the AI Agent and the question bank search."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.core.errors import ConflictError, NotFoundError
from app.core.security import create_access_token
from app.db.session import get_db
from app.graphs.recruiter import graph as recruiter
from app.main import create_app
from app.mcp_servers import rag_server
from app.models import Candidate, InterviewSession, Job, ScreeningResult
from app.models.enums import CandidateStatus, SessionStatus, UserRole
from app.services import interview_chat_service, interview_context, question_service
from app.services.question_service import QuestionBatch, SuggestedQuestion

START = datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)
PRIVATE = ["nadia@example.com", "+880 1712 345678", "linkedin.com/in/nadia"]


def _session(status: str = SessionStatus.IN_PROGRESS) -> InterviewSession:
    session = InterviewSession(
        id=9,
        candidate_id=5,
        job_id=2,
        scheduled_start=START,
        scheduled_end=START + timedelta(minutes=45),
        join_token_hash="hash",
        status=status,
    )
    candidate = Candidate(
        id=5,
        job_id=2,
        full_name="Nadia Karim",
        email="nadia@example.com",
        status=CandidateStatus.INTERVIEW_SCHEDULED,
        cv_parsed={
            "skills": ["Python", "Docker"],
            "contact": {"emails": [PRIVATE[0]], "phones": [PRIVATE[1]], "links": [PRIVATE[2]]},
        },
    )
    candidate.screening_result = ScreeningResult(
        candidate_id=5,
        final_score=88.4,
        final_rank=1,
        justification="Strong on APIs.",
        requirement_matches=[
            {
                "id": "R1",
                "status": "partially_met",
                "evidence": "Docker Compose",
                "reason": "local only",
            }
        ],
    )
    session.candidate = candidate
    return session


def _job() -> Job:
    return Job(
        id=2,
        job_code="HL-BE-01",
        title="Backend Engineer",
        requirements={
            "min_experience_years": 2,
            "items": [{"id": "R1", "text": "Docker in production", "priority": "must_have"}],
        },
    )


class FakeDB:
    def __init__(self, session: InterviewSession):
        self.session = session
        self.job = _job()
        self.commits = 0

    def get(self, model, key):
        if model is Job:
            return self.job if key == self.job.id else None
        return self.session if key == self.session.id else None

    def commit(self):
        self.commits += 1


def _batch(count: int = 5, requirement_id: str | None = "R1") -> QuestionBatch:
    return QuestionBatch(
        questions=[
            SuggestedQuestion(
                requirement_id=requirement_id,
                reason="partly_met",
                question=f"How would you run service {number} in production?",
                why="the CV shows local use only",
            )
            for number in range(count)
        ]
    )


@pytest.fixture()
def prompts(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The prompts sent to the AI, with a scripted answer of five questions."""
    sent: list[str] = []

    def fake_generate(prompt: str, schema):
        sent.append(prompt)
        return _batch(requirement_id="R1" if len(sent) == 1 else "R99")

    monkeypatch.setattr(question_service.ai_client, "generate_structured", fake_generate)
    return sent


# --- What the AI is told ---


def test_the_ai_is_told_the_job_and_cv_but_no_contact_details() -> None:
    db = FakeDB(_session())

    details = interview_context.describe(db, db.session)

    assert "Backend Engineer" in details and "Docker in production" in details
    assert "Nadia Karim" in details and "partially_met" in details
    for private in PRIVATE:
        assert private not in details


# --- Suggested questions ---


def test_five_questions_are_suggested_and_saved(prompts: list[str]) -> None:
    db = FakeDB(_session())

    questions = question_service.generate(db, 9)

    assert len(questions) == 5 and db.commits == 1
    assert [item["id"] for item in questions] == [1, 2, 3, 4, 5]
    assert questions[0]["requirement"] == "Docker in production"
    assert questions[0]["asked"] is False
    for private in PRIVATE:
        assert private not in prompts[0]


def test_more_questions_continue_without_repeats(prompts: list[str]) -> None:
    db = FakeDB(_session())
    question_service.generate(db, 9)

    questions = question_service.generate(db, 9)

    assert len(questions) == 10 and questions[5]["id"] == 6
    assert "Do not repeat them" in prompts[1]
    assert "service 0 in production" in prompts[1]
    # An unknown requirement id from the AI is dropped.
    assert questions[5]["requirement_id"] is None


def test_suggestions_stop_at_the_limit(prompts: list[str]) -> None:
    session = _session()
    session.suggested_questions = [
        {"id": number, "question": "q", "asked": False}
        for number in range(1, question_service.MAX_QUESTIONS + 1)
    ]

    with pytest.raises(ConflictError, match="most suggested"):
        question_service.generate(FakeDB(session), 9)
    assert prompts == []


@pytest.mark.parametrize("status", [SessionStatus.COMPLETED, SessionStatus.CANCELLED])
def test_no_questions_after_the_interview(prompts: list[str], status: str) -> None:
    with pytest.raises(ConflictError, match="ended or was cancelled"):
        question_service.generate(FakeDB(_session(status)), 9)


def test_a_question_can_be_marked_as_asked_and_back(prompts: list[str]) -> None:
    db = FakeDB(_session())
    question_service.generate(db, 9)

    assert question_service.mark_asked(db, 9, 2, True)[1]["asked"] is True
    assert question_service.mark_asked(db, 9, 2, False)[1]["asked"] is False
    with pytest.raises(NotFoundError):
        question_service.mark_asked(db, 9, 99, True)


# --- The read-only chat ---


def _interview_graph(monkeypatch: pytest.MonkeyPatch, replies: list[AIMessage]):
    model = FakeMessagesListChatModel(responses=replies)
    monkeypatch.setattr(recruiter, "get_interview_model", lambda: model)
    monkeypatch.setattr(
        interview_context, "for_session", lambda session_id: ("details", "Backend Engineer")
    )
    return recruiter.build_recruiter_graph(InMemorySaver())


def _call(name: str, args: dict, call_id: str = "call-1") -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def test_the_chat_answers_and_keeps_its_history(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = _interview_graph(monkeypatch, [AIMessage("Docker is partly met.")])
    db = FakeDB(_session())

    chat = interview_chat_service.send(db, graph, 9, 1, "What is weak?")

    assert chat == [
        {"role": "interviewer", "text": "What is weak?"},
        {"role": "agent", "text": "Docker is partly met.", "from_question_bank": False},
    ]
    assert interview_chat_service.read(db, graph, 9) == chat


def test_the_chat_can_never_change_anything(monkeypatch: pytest.MonkeyPatch) -> None:
    scheduled: list = []
    monkeypatch.setitem(
        recruiter.TOOL_HANDLERS,
        "CancelInterview",
        lambda arguments, state: scheduled.append(arguments) or ("done", {}),
    )
    graph = _interview_graph(
        monkeypatch,
        [_call("CancelInterview", {"session_id": 9}), AIMessage("I cannot do that here.")],
    )

    chat = interview_chat_service.send(FakeDB(_session()), graph, 9, 1, "Cancel it")

    assert scheduled == []
    state = graph.get_state({"configurable": {"thread_id": "interview-9"}})
    assert state.next == ()
    assert recruiter.NOT_IN_INTERVIEW in [message.text for message in state.values["messages"]]
    assert chat[-1]["text"] == "I cannot do that here."


def test_bank_answers_are_marked_and_kept_to_the_role(monkeypatch: pytest.MonkeyPatch) -> None:
    searched: list[dict] = []

    def fake_call(name: str, arguments: dict) -> list:
        searched.append(arguments)
        return [{"question": "How do you roll back?", "source": "q.txt"}]

    monkeypatch.setattr(recruiter.mcp_client, "call_tool", fake_call)
    graph = _interview_graph(
        monkeypatch,
        [
            # The model cannot choose another role's questions.
            _call("search_question_bank", {"query": "kubernetes", "role": "Data Analyst"}),
            AIMessage("From the question bank: How do you roll back?"),
        ],
    )

    chat = interview_chat_service.send(FakeDB(_session()), graph, 9, 1, "A k8s question")

    assert chat[-1]["from_question_bank"] is True
    assert searched == [{"query": "kubernetes", "role": "Backend Engineer"}]


def test_the_chat_is_closed_after_the_interview(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = _interview_graph(monkeypatch, [AIMessage("unused")])

    with pytest.raises(ConflictError):
        interview_chat_service.send(FakeDB(_session(SessionStatus.COMPLETED)), graph, 9, 1, "Hi")


def test_each_mode_gets_its_own_search_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string"}, "role": {"type": "string"}},
        "required": ["query"],
    }
    tools = [
        {"type": "function", "function": {"name": name, "parameters": parameters}}
        for name in ("search_jd_references", "search_question_bank")
    ]
    monkeypatch.setattr(recruiter.mcp_client, "tool_definitions", lambda: tools)

    interview_tools = recruiter._mcp_tools(interview=True)
    assert [t["function"]["name"] for t in interview_tools] == ["search_question_bank"]
    # The role is filled in by the application, so the model never sees it.
    assert list(interview_tools[0]["function"]["parameters"]["properties"]) == ["query"]
    assert [t["function"]["name"] for t in recruiter._mcp_tools(interview=False)] == [
        "search_jd_references"
    ]


# --- The question bank search ---


def _bank_match(text: str, tags: str, distance: float = 0.2) -> dict:
    return {"text": text, "metadata": {"source": "q.txt", "tags": tags}, "distance": distance}


def test_the_question_bank_keeps_this_roles_and_general_questions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    searched: list[str] = []

    def fake_search(collection: str, query: str, limit: int) -> list:
        searched.append(collection)
        return [
            _bank_match("Backend question", "Backend Engineer"),
            _bank_match("Shared question", "Data Analyst, backend engineer"),
            _bank_match("ML question", "Machine Learning Engineer"),
            _bank_match("General question", ""),
            _bank_match("Too far", "Backend Engineer", distance=0.95),
        ]

    monkeypatch.setattr(rag_server.store, "search", fake_search)

    # A role counts when it is part of the job title, in any case.
    found = rag_server.find_bank_questions("kubernetes", "Senior Backend Engineer (Python)")

    assert searched == [rag_server.store.QUESTION_BANK]
    assert [item["question"] for item in found] == [
        "Backend question",
        "Shared question",
        "General question",
    ]
    assert found[0]["similarity"] == 0.8


# --- Who may use it ---


def _auth(role: UserRole) -> dict[str, str]:
    token = create_access_token(subject="1", role=role, expires_in=timedelta(minutes=5))
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", "questions"), ("post", "questions"), ("get", "chat"), ("post", "chat")],
)
def test_only_the_interviewer_uses_the_ai_help(method: str, path: str) -> None:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: FakeDB(_session())
    client = TestClient(app)
    body = {"json": {"message": "Hi"}} if path == "chat" and method == "post" else {}

    assert getattr(client, method)(f"/interviews/9/{path}", **body).status_code == 401
    response = getattr(client, method)(
        f"/interviews/9/{path}", headers=_auth(UserRole.CANDIDATE), **body
    )
    assert response.status_code == 403


def test_saved_questions_are_listed(prompts: list[str]) -> None:
    db = FakeDB(_session())
    question_service.generate(db, 9)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    response = client.get("/interviews/9/questions", headers=_auth(UserRole.INTERVIEWER))

    assert response.status_code == 200
    assert len(response.json()) == 5
    assert json.dumps(response.json()).count('"asked": false') == 5
