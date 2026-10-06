"""Tests for the chat WebSocket, using a scripted fake model."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models import (
    FakeMessagesListChatModel,
    GenericFakeChatModel,
)
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token
from app.graphs.recruiter import graph as recruiter
from app.main import create_app
from app.models.enums import UserRole
from tests.test_recruiter_agent import VALID_ARGS, _save_call


def _token(role: UserRole = UserRole.INTERVIEWER) -> str:
    return create_access_token("1", role, timedelta(minutes=5))


@pytest.fixture()
def client_with(monkeypatch: pytest.MonkeyPatch):
    def build(replies: list[AIMessage], streaming: bool = False) -> TestClient:
        # Only the streaming fake sends a reply piece by piece, and only the
        # other one can return tool calls, so each test picks what it needs.
        if streaming:
            model = GenericFakeChatModel(messages=iter(replies))
        else:
            model = FakeMessagesListChatModel(responses=replies)
        monkeypatch.setattr(recruiter, "get_agent_model", lambda: model)
        monkeypatch.setitem(
            recruiter.TOOL_HANDLERS,
            "SaveJob",
            lambda arguments, state: ("Job saved with job code HL-BE-01.", {"saved_job_id": 7}),
        )
        graph = recruiter.build_recruiter_graph(InMemorySaver())
        app = create_app()
        app.dependency_overrides[recruiter.get_recruiter_graph] = lambda: graph
        return TestClient(app)

    return build


def _read_turn(socket) -> tuple[str, dict]:
    """Collect the streamed pieces until the finished turn arrives."""
    pieces = []
    while True:
        event = socket.receive_json()
        if event["type"] == "token":
            pieces.append(event["text"])
        else:
            return "".join(pieces), event


def test_reply_is_streamed_then_completed(client_with) -> None:
    client = client_with(
        [AIMessage("Here is a draft job description.")], streaming=True
    )

    with client.websocket_connect("/chat") as socket:
        socket.send_json({"type": "auth", "token": _token()})
        assert socket.receive_json() == {"type": "ready"}

        socket.send_json({"type": "message", "text": "I need a backend engineer"})
        streamed, turn = _read_turn(socket)

    assert streamed == "Here is a draft job description."
    assert turn["type"] == "turn"
    assert turn["status"] == "replied"
    assert turn["reply"] == "Here is a draft job description."


def test_approval_over_the_socket_saves_the_job(client_with) -> None:
    client = client_with([_save_call(VALID_ARGS), AIMessage("Saved as HL-BE-01.")])

    with client.websocket_connect("/chat") as socket:
        socket.send_json({"type": "auth", "token": _token()})
        socket.receive_json()

        socket.send_json({"type": "message", "text": "I approve"})
        _, waiting = _read_turn(socket)
        assert waiting["status"] == "waiting_for_approval"
        assert waiting["pending_action"]["action"] == "SaveJob"

        socket.send_json(
            {"type": "approval", "thread_id": waiting["thread_id"], "approved": True}
        )
        _, done = _read_turn(socket)

    assert done["status"] == "replied"
    assert done["job_id"] == 7


def test_connection_is_closed_without_a_valid_token(client_with) -> None:
    client = client_with([])

    with client.websocket_connect("/chat") as socket:
        socket.send_json({"type": "auth", "token": "not-a-token"})
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()


def test_candidate_token_is_refused(client_with) -> None:
    client = client_with([])

    with client.websocket_connect("/chat") as socket:
        socket.send_json({"type": "auth", "token": _token(UserRole.CANDIDATE)})
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()


def test_problems_are_reported_as_error_events(client_with) -> None:
    client = client_with([])

    with client.websocket_connect("/chat") as socket:
        socket.send_json({"type": "auth", "token": _token()})
        socket.receive_json()

        socket.send_json({"type": "approval", "thread_id": "unknown", "approved": True})
        event = socket.receive_json()

    assert event == {"type": "error", "message": "This conversation does not exist."}