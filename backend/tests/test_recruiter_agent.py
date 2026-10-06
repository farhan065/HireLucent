"""Tests for the Recruiter Agent graph, using a scripted fake model."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.core.errors import ConflictError
from app.graphs.base import thread_config
from app.graphs.recruiter import graph as recruiter
from app.graphs.recruiter.drafts import latest_draft, parse_draft
from app.graphs.recruiter.prompts import ERROR_REPLY
from app.graphs.recruiter.tools import save_job
from tests.helpers import (
    BAD_ARGS,
    DRAFT_ONE,
    VALID_ARGS,
    graph_with_replies,
    save_call,
    search_call,
)


def _send(graph, config: dict, text: str) -> None:
    graph.invoke({"messages": [HumanMessage(text)], "user_id": 1}, config)


def test_plain_answer_goes_straight_to_respond(monkeypatch) -> None:
    saved: list[dict] = []
    graph = graph_with_replies(monkeypatch, [AIMessage(DRAFT_ONE)], saved)
    config = thread_config("t1")

    _send(graph, config, "I need a backend engineer")

    state = graph.get_state(config)
    assert state.next == ()
    assert latest_draft(state.values["messages"]).title == "Backend Engineer"
    assert saved == []


def test_saving_waits_for_approval_then_runs(monkeypatch) -> None:
    saved: list[dict] = []
    graph = graph_with_replies(
        monkeypatch, [save_call(VALID_ARGS), AIMessage("Saved as HL-BE-01.")], saved
    )
    config = thread_config("t2")

    _send(graph, config, "I approve")
    assert graph.get_state(config).next == ("human_approval",)
    assert saved == []

    graph.invoke(Command(resume={"approved": True}), config)
    finished = graph.get_state(config)
    assert finished.next == ()
    assert finished.values["saved_job_id"] == 7
    assert saved[0]["user_id"] == 1


def test_interviewer_edits_are_used_when_approving(monkeypatch) -> None:
    saved: list[dict] = []
    graph = graph_with_replies(
        monkeypatch, [save_call(VALID_ARGS), AIMessage("Saved.")], saved
    )
    config = thread_config("t3")
    edited = {
        **VALID_ARGS,
        "scoring_weights": {
            "technical_skills": 0.6,
            "experience": 0.3,
            "qualifications": 0.1,
        },
    }

    _send(graph, config, "I approve")
    graph.invoke(Command(resume={"approved": True, "arguments": edited}), config)

    assert saved[0]["arguments"]["scoring_weights"]["technical_skills"] == 0.6


def test_rejection_returns_to_the_agent_without_saving(monkeypatch) -> None:
    saved: list[dict] = []
    graph = graph_with_replies(
        monkeypatch, [save_call(VALID_ARGS), AIMessage("What should I change?")], saved
    )
    config = thread_config("t4")

    _send(graph, config, "I approve")
    graph.invoke(Command(resume={"approved": False, "feedback": "Add Docker"}), config)

    state = graph.get_state(config)
    assert state.next == ()
    assert saved == []
    assert "Add Docker" in state.values["messages"][-2].content


def test_invalid_details_are_corrected_before_the_interviewer_sees_them(
    monkeypatch,
) -> None:
    saved: list[dict] = []
    graph = graph_with_replies(
        monkeypatch,
        [save_call(BAD_ARGS, "c1"), save_call(VALID_ARGS, "c2"), AIMessage("Saved.")],
        saved,
    )
    config = thread_config("t5")

    _send(graph, config, "I approve")
    paused = graph.get_state(config)
    assert paused.next == ("human_approval",)
    assert paused.values["attempts"] == 1
    shown = paused.tasks[0].interrupts[0].value["arguments"]
    assert shown["scoring_weights"] == VALID_ARGS["scoring_weights"]

    graph.invoke(Command(resume={"approved": True}), config)
    assert graph.get_state(config).next == ()
    assert len(saved) == 1


def test_missing_details_are_filled_in_or_sent_back(monkeypatch) -> None:
    incomplete = {
        **VALID_ARGS,
        "requirements": {"items": VALID_ARGS["requirements"]["items"]},
    }
    graph = graph_with_replies(
        monkeypatch, [save_call(incomplete, "c1"), save_call(VALID_ARGS, "c2")]
    )
    config = thread_config("t5b")

    _send(graph, config, "I approve")

    shown = graph.get_state(config).tasks[0].interrupts[0].value["arguments"]
    assert shown["requirements"]["min_experience_years"] == 2


def test_repeated_failures_end_with_a_clear_message(monkeypatch) -> None:
    saved: list[dict] = []
    graph = graph_with_replies(
        monkeypatch, [save_call(BAD_ARGS, f"c{i}") for i in range(3)], saved
    )
    config = thread_config("t6")

    _send(graph, config, "I approve")

    state = graph.get_state(config)
    assert state.next == ()
    assert saved == []
    assert state.values["messages"][-1].content == ERROR_REPLY


def test_model_failure_gives_a_clear_message(monkeypatch) -> None:
    def broken_model():
        raise ConnectionError("no network")

    monkeypatch.setattr(recruiter, "get_agent_model", broken_model)
    monkeypatch.setattr(recruiter, "run_with_retries", lambda operation, call: call())
    graph = recruiter.build_recruiter_graph(InMemorySaver())
    config = thread_config("t7")

    _send(graph, config, "Hello")

    assert graph.get_state(config).values["messages"][-1].content == ERROR_REPLY


def test_draft_is_found_after_an_introduction() -> None:
    draft = parse_draft("Here is a draft.\n# Backend Engineer\n\n## About\nBuild APIs.")

    assert draft.preamble == "Here is a draft."
    assert draft.title == "Backend Engineer"
    assert draft.body == "## About\nBuild APIs."


def test_a_plain_reply_is_not_a_draft() -> None:
    assert parse_draft("Which seniority level do you need?") is None


def test_a_conversation_cannot_save_a_second_job() -> None:
    state = {"saved_job_id": 7, "user_id": 1, "messages": [AIMessage(DRAFT_ONE)]}

    with pytest.raises(ConflictError):
        save_job(VALID_ARGS, state)


def test_saving_needs_a_description() -> None:
    state = {"user_id": 1, "messages": [HumanMessage("I approve")]}

    with pytest.raises(ConflictError):
        save_job(VALID_ARGS, state)


def test_search_runs_without_approval_and_its_result_reaches_the_model(
    monkeypatch,
) -> None:
    calls = []

    def fake_call_tool(name: str, arguments: dict) -> list[dict]:
        calls.append((name, arguments))
        return [{"source": "backend.txt", "similarity": 0.8, "text": "Template text"}]

    monkeypatch.setattr(recruiter.mcp_client, "call_tool", fake_call_tool)
    graph = graph_with_replies(monkeypatch, [search_call(), AIMessage(DRAFT_ONE)])
    config = thread_config("t8")

    _send(graph, config, "I need a backend engineer")

    state = graph.get_state(config)
    assert state.next == ()
    assert calls == [("search_jd_references", {"query": "backend engineer python"})]
    assert "backend.txt" in state.values["messages"][-2].content
    assert latest_draft(state.values["messages"]).title == "Backend Engineer"


def test_the_assistant_continues_when_search_is_unavailable(monkeypatch) -> None:
    def broken_call_tool(name: str, arguments: dict) -> list[dict]:
        raise ConnectionError("server down")

    monkeypatch.setattr(recruiter.mcp_client, "call_tool", broken_call_tool)
    graph = graph_with_replies(monkeypatch, [search_call(), AIMessage(DRAFT_ONE)])
    config = thread_config("t9")

    _send(graph, config, "I need a backend engineer")

    state = graph.get_state(config)
    assert state.values["messages"][-2].content == recruiter.SEARCH_UNAVAILABLE
    assert latest_draft(state.values["messages"]).title == "Backend Engineer"
