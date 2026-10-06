"""Tests for the chat service and the conversation view."""

import pytest
from langchain_core.messages import AIMessage

from app.core.errors import ConflictError, NotFoundError
from app.services import chat_service
from app.graphs.recruiter import graph as recruiter
from tests.helpers import (
    DRAFT_ONE,
    DRAFT_TWO,
    VALID_ARGS,
    graph_with_replies,
    save_call,
    search_call,
)


def _kinds(view) -> list[str]:
    return [item.kind for item in view.items]


def test_first_draft_is_shown_as_a_description_card(monkeypatch) -> None:
    graph = graph_with_replies(monkeypatch, [AIMessage(DRAFT_ONE)])

    view = chat_service.send_message(graph, 1, None, "I need a backend engineer")

    assert view.stage == "reviewing_description"
    assert view.title == "Backend Engineer"
    assert _kinds(view) == ["user", "description"]
    card = view.items[-1]
    assert (card.version, card.status, card.title) == (1, "waiting", "Backend Engineer")
    assert view.brief.description.status == "waiting"


def test_a_question_from_the_assistant_is_a_normal_reply(monkeypatch) -> None:
    graph = graph_with_replies(monkeypatch, [AIMessage("Which seniority level?")])

    view = chat_service.send_message(graph, 1, None, "I need an engineer")

    assert view.stage == "describing"
    assert _kinds(view) == ["user", "assistant"]
    assert view.brief.description is None


def test_a_revision_replaces_the_earlier_draft(monkeypatch) -> None:
    graph = graph_with_replies(monkeypatch, [AIMessage(DRAFT_ONE), AIMessage(DRAFT_TWO)])

    first = chat_service.send_message(graph, 1, None, "I need a backend engineer")
    view = chat_service.send_message(graph, 1, first.thread_id, "Make it senior")

    cards = [item for item in view.items if item.kind == "description"]
    assert [(card.version, card.status) for card in cards] == [
        (1, "replaced"),
        (2, "waiting"),
    ]
    assert view.brief.description.title == "Senior Backend Engineer"


def test_direct_edit_becomes_a_new_draft_without_calling_the_model(monkeypatch) -> None:
    graph = graph_with_replies(monkeypatch, [AIMessage(DRAFT_ONE)])
    first = chat_service.send_message(graph, 1, None, "I need a backend engineer")

    view = chat_service.edit_description(
        graph, 1, first.thread_id, "Backend Engineer (Python)", "## About\nEdited text."
    )

    assert _kinds(view)[-2:] == ["note", "description"]
    assert "Saved as draft 2" in view.items[-2].text
    card = view.items[-1]
    assert (card.version, card.status) == (2, "waiting")
    assert card.title == "Backend Engineer (Python)"
    assert card.text == "## About\nEdited text."
    assert view.stage == "reviewing_description"


def test_approval_flow_saves_the_job(monkeypatch) -> None:
    saved: list[dict] = []
    graph = graph_with_replies(
        monkeypatch,
        [AIMessage(DRAFT_ONE), save_call(VALID_ARGS), AIMessage("Saved as HL-BE-01.")],
        saved,
    )
    first = chat_service.send_message(graph, 1, None, "I need a backend engineer")

    waiting = chat_service.send_message(graph, 1, first.thread_id, "I approve this.")
    assert waiting.stage == "confirming_requirements"
    assert waiting.items[-1].kind == "requirements"
    assert waiting.items[-1].status == "waiting"
    assert waiting.brief.requirements_status == "proposed"
    assert waiting.brief.description.status == "approved"
    assert saved == []

    done = chat_service.submit_approval(graph, 1, first.thread_id, True, None, None)
    assert done.stage == "saved"
    assert done.brief.job_id == 7
    assert done.brief.job_code == "HL-BE-01"
    assert done.brief.requirements_status == "confirmed"
    assert done.items[-1].text == "Saved as HL-BE-01."
    assert len(saved) == 1


def test_typing_a_clear_yes_confirms(monkeypatch) -> None:
    saved: list[dict] = []
    graph = graph_with_replies(
        monkeypatch,
        [AIMessage(DRAFT_ONE), save_call(VALID_ARGS), AIMessage("Saved.")],
        saved,
    )
    first = chat_service.send_message(graph, 1, None, "I need a backend engineer")
    chat_service.send_message(graph, 1, first.thread_id, "I approve this.")

    done = chat_service.send_message(graph, 1, first.thread_id, "Looks good, save it")

    assert done.stage == "saved"
    assert len(saved) == 1


def test_any_other_message_while_waiting_is_a_change_request(monkeypatch) -> None:
    saved: list[dict] = []
    graph = graph_with_replies(
        monkeypatch,
        [AIMessage(DRAFT_ONE), save_call(VALID_ARGS), AIMessage("What should change?")],
        saved,
    )
    first = chat_service.send_message(graph, 1, None, "I need a backend engineer")
    chat_service.send_message(graph, 1, first.thread_id, "I approve this.")

    after = chat_service.send_message(
        graph, 1, first.thread_id, "Yes, but make Docker a must-have"
    )

    assert saved == []
    assert after.stage == "reviewing_description"
    card = next(item for item in after.items if item.kind == "requirements")
    assert card.status == "changed"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("yes", True),
        ("Looks good, save it", True),
        ("Confirm.", True),
        ("Yes, but add Docker", False),
        ("Make Docker a must-have", False),
        ("ok change the weights", False),
    ],
)
def test_clear_yes_detection(text: str, expected: bool) -> None:
    assert chat_service.is_clear_yes(text) is expected


def test_conversation_can_be_reopened_with_its_history(monkeypatch) -> None:
    graph = graph_with_replies(monkeypatch, [AIMessage(DRAFT_ONE)])
    first = chat_service.send_message(graph, 1, None, "I need a backend engineer")

    reopened = chat_service.get_conversation(graph, 1, first.thread_id)

    assert reopened == first


def test_another_user_cannot_open_the_conversation(monkeypatch) -> None:
    graph = graph_with_replies(monkeypatch, [AIMessage(DRAFT_ONE)])
    first = chat_service.send_message(graph, 1, None, "Hello")

    with pytest.raises(NotFoundError):
        chat_service.get_conversation(graph, 2, first.thread_id)


def test_approval_without_a_pending_action_is_refused(monkeypatch) -> None:
    graph = graph_with_replies(monkeypatch, [AIMessage(DRAFT_ONE)])
    first = chat_service.send_message(graph, 1, None, "Hello")

    with pytest.raises(ConflictError):
        chat_service.submit_approval(graph, 1, first.thread_id, True, None, None)


def test_a_search_is_shown_as_a_note_with_the_templates_used(monkeypatch) -> None:
    monkeypatch.setattr(
        recruiter.mcp_client,
        "call_tool",
        lambda name, arguments: [{"source": "backend.txt", "similarity": 0.8, "text": "T"}],
    )
    graph = graph_with_replies(
        monkeypatch, [search_call(), AIMessage("Based on: backend.txt\n" + DRAFT_ONE)]
    )

    view = chat_service.send_message(graph, 1, None, "I need a backend engineer")

    assert _kinds(view) == ["user", "note", "assistant", "description"]
    assert view.items[1].text == "Checked your Knowledge Base. Using: backend.txt"
    assert view.items[2].text == "Based on: backend.txt"
    assert view.stage == "reviewing_description"


def test_a_search_with_no_match_says_so(monkeypatch) -> None:
    monkeypatch.setattr(recruiter.mcp_client, "call_tool", lambda name, arguments: [])
    graph = graph_with_replies(monkeypatch, [search_call(), AIMessage(DRAFT_ONE)])

    view = chat_service.send_message(graph, 1, None, "I need a pastry chef")

    assert view.items[1].text == "Checked your Knowledge Base. No similar template found."


def test_an_unavailable_search_is_reported_plainly(monkeypatch) -> None:
    def broken_call_tool(name: str, arguments: dict) -> list[dict]:
        raise ConnectionError("server down")

    monkeypatch.setattr(recruiter.mcp_client, "call_tool", broken_call_tool)
    graph = graph_with_replies(monkeypatch, [search_call(), AIMessage(DRAFT_ONE)])

    view = chat_service.send_message(graph, 1, None, "I need a backend engineer")

    assert view.items[1].text == "The Knowledge Base search was not available."
    assert view.items[-1].kind == "description"
