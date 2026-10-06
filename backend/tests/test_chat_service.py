"""Tests for the chat service, using a scripted fake model."""

import pytest
from langchain_core.language_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.core.errors import ConflictError, NotFoundError
from app.graphs.recruiter import graph as recruiter
from app.services import chat_service
from tests.test_recruiter_agent import VALID_ARGS, _save_call


@pytest.fixture()
def graph_with(monkeypatch: pytest.MonkeyPatch):
    def build(replies: list[AIMessage]):
        model = FakeMessagesListChatModel(responses=replies)
        monkeypatch.setattr(recruiter, "get_agent_model", lambda: model)
        monkeypatch.setitem(
            recruiter.TOOL_HANDLERS,
            "SaveJob",
            lambda arguments, state: ("Job saved with job code HL-BE-01.", {"saved_job_id": 7}),
        )
        return recruiter.build_recruiter_graph(InMemorySaver())

    return build


def test_conversation_continues_in_the_same_thread(graph_with) -> None:
    graph = graph_with([AIMessage("Draft one."), AIMessage("Draft two.")])

    first = chat_service.send_message(graph, 1, None, "I need a backend engineer")
    second = chat_service.send_message(graph, 1, first.thread_id, "Make it senior")

    assert first.status == "replied"
    assert first.reply == "Draft one."
    assert second.thread_id == first.thread_id
    assert second.reply == "Draft two."


def test_approval_flow_returns_the_saved_job(graph_with) -> None:
    graph = graph_with([_save_call(VALID_ARGS), AIMessage("Saved as HL-BE-01.")])

    waiting = chat_service.send_message(graph, 1, None, "I approve")
    assert waiting.status == "waiting_for_approval"
    assert waiting.pending_action.action == "SaveJob"
    assert waiting.pending_action.arguments["title"] == "Backend Engineer"

    done = chat_service.submit_approval(graph, 1, waiting.thread_id, True, None, None)
    assert done.status == "replied"
    assert done.job_id == 7
    assert done.reply == "Saved as HL-BE-01."


def test_a_new_message_while_waiting_counts_as_a_change_request(graph_with) -> None:
    graph = graph_with([_save_call(VALID_ARGS), AIMessage("Updated the draft.")])

    waiting = chat_service.send_message(graph, 1, None, "I approve")
    after = chat_service.send_message(graph, 1, waiting.thread_id, "Wait, add Docker")

    assert after.status == "replied"
    assert after.job_id is None
    assert after.reply == "Updated the draft."


def test_another_user_cannot_use_the_conversation(graph_with) -> None:
    graph = graph_with([AIMessage("Draft.")])
    first = chat_service.send_message(graph, 1, None, "Hello")

    with pytest.raises(NotFoundError):
        chat_service.send_message(graph, 2, first.thread_id, "Hello")


def test_approval_without_a_pending_action_is_refused(graph_with) -> None:
    graph = graph_with([AIMessage("Draft.")])
    first = chat_service.send_message(graph, 1, None, "Hello")

    with pytest.raises(ConflictError):
        chat_service.submit_approval(graph, 1, first.thread_id, True, None, None)