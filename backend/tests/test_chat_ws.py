"""Tests for the chat WebSocket, using a scripted fake model."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token
from app.graphs.recruiter import graph as recruiter
from app.main import create_app
from app.models.enums import UserRole
from tests.helpers import DRAFT_ONE, VALID_ARGS, graph_with_replies, save_call


def _token(role: UserRole = UserRole.INTERVIEWER) -> str:
    return create_access_token("1", role, timedelta(minutes=5))


def _client(graph) -> TestClient:
    app = create_app()
    app.dependency_overrides[recruiter.get_recruiter_graph] = lambda: graph
    return TestClient(app)


def _read_turn(socket) -> tuple[str, dict]:
    """Collect the streamed pieces until the finished view arrives."""
    pieces = []
    while True:
        event = socket.receive_json()
        if event["type"] == "token":
            pieces.append(event["text"])
        else:
            return "".join(pieces), event


def test_reply_is_streamed_then_the_view_arrives(monkeypatch) -> None:
    # This fake model sends its reply piece by piece, like a real one.
    model = GenericFakeChatModel(messages=iter([AIMessage("Which seniority level?")]))
    monkeypatch.setattr(recruiter, "get_agent_model", lambda: model)
    client = _client(recruiter.build_recruiter_graph(InMemorySaver()))

    with client.websocket_connect("/chat") as socket:
        socket.send_json({"type": "auth", "token": _token()})
        assert socket.receive_json() == {"type": "ready"}

        socket.send_json({"type": "message", "text": "I need an engineer"})
        streamed, view = _read_turn(socket)

    assert streamed == "Which seniority level?"
    assert view["type"] == "view"
    assert view["stage"] == "describing"
    assert view["items"][-1]["text"] == "Which seniority level?"


def test_approval_and_edit_work_over_the_socket(monkeypatch) -> None:
    graph = graph_with_replies(
        monkeypatch, [AIMessage(DRAFT_ONE), save_call(VALID_ARGS), AIMessage("Saved.")]
    )
    client = _client(graph)

    with client.websocket_connect("/chat") as socket:
        socket.send_json({"type": "auth", "token": _token()})
        socket.receive_json()

        socket.send_json({"type": "message", "text": "I need a backend engineer"})
        _, first = _read_turn(socket)
        thread_id = first["thread_id"]

        socket.send_json(
            {
                "type": "edit_description",
                "thread_id": thread_id,
                "title": "Backend Engineer (Python)",
                "text": "## About\nEdited by the interviewer.",
            }
        )
        _, edited = _read_turn(socket)
        assert edited["brief"]["description"]["version"] == 2

        socket.send_json({"type": "message", "thread_id": thread_id, "text": "I approve"})
        _, waiting = _read_turn(socket)
        assert waiting["stage"] == "confirming_requirements"

        socket.send_json({"type": "approval", "thread_id": thread_id, "approved": True})
        _, done = _read_turn(socket)

    assert done["stage"] == "saved"
    assert done["brief"]["job_code"] == "HL-BE-01"


def test_connection_is_closed_without_a_valid_token(monkeypatch) -> None:
    client = _client(graph_with_replies(monkeypatch, []))

    with client.websocket_connect("/chat") as socket:
        socket.send_json({"type": "auth", "token": "not-a-token"})
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()


def test_candidate_token_is_refused(monkeypatch) -> None:
    client = _client(graph_with_replies(monkeypatch, []))

    with client.websocket_connect("/chat") as socket:
        socket.send_json({"type": "auth", "token": _token(UserRole.CANDIDATE)})
        with pytest.raises(WebSocketDisconnect):
            socket.receive_json()


def test_problems_are_reported_as_error_events(monkeypatch) -> None:
    client = _client(graph_with_replies(monkeypatch, []))

    with client.websocket_connect("/chat") as socket:
        socket.send_json({"type": "auth", "token": _token()})
        socket.receive_json()

        socket.send_json({"type": "approval", "thread_id": "unknown", "approved": True})
        event = socket.receive_json()

    assert event == {"type": "error", "message": "This conversation does not exist."}
