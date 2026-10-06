"""Tests for the Recruiter Agent graph, using a scripted fake model."""

import pytest
from langchain_core.language_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.graphs.base import thread_config
from app.graphs.recruiter import graph as recruiter
from app.graphs.recruiter.prompts import ERROR_REPLY

VALID_ARGS = {
    "title": "Backend Engineer",
    "jd_text": "We are hiring a Backend Engineer to build and maintain REST APIs.",
    "requirements": {
        "min_experience_years": 2,
        "items": [
            {
                "id": "R1",
                "text": "Python web development",
                "category": "technical_skills",
                "priority": "must_have",
                "keywords": ["python", "django"],
            }
        ],
    },
    "scoring_weights": {"technical_skills": 0.5, "experience": 0.3, "qualifications": 0.2},
}


def _save_call(args: dict, call_id: str = "call-1") -> AIMessage:
    return AIMessage(
        content="", tool_calls=[{"name": "SaveJob", "args": args, "id": call_id}]
    )


@pytest.fixture()
def saved_jobs(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Replace the real save tool with one that records what it was given."""
    saved: list[dict] = []

    def fake_save_job(arguments: dict, state: dict) -> tuple[str, dict]:
        recruiter.TOOL_SCHEMAS[0].model_validate(arguments)
        saved.append({"arguments": arguments, "user_id": state["user_id"]})
        return "Job saved with job code HL-BE-01.", {"saved_job_id": 7}

    monkeypatch.setitem(recruiter.TOOL_HANDLERS, "SaveJob", fake_save_job)
    return saved


def _graph_with_replies(monkeypatch: pytest.MonkeyPatch, replies: list[AIMessage]):
    model = FakeMessagesListChatModel(responses=replies)
    monkeypatch.setattr(recruiter, "get_agent_model", lambda: model)
    return recruiter.build_recruiter_graph(InMemorySaver())


def _send(graph, config: dict, text: str) -> None:
    graph.invoke({"messages": [HumanMessage(text)], "user_id": 1}, config)


def test_plain_answer_goes_straight_to_respond(monkeypatch, saved_jobs) -> None:
    graph = _graph_with_replies(monkeypatch, [AIMessage("Here is a draft.")])
    config = thread_config("t1")

    _send(graph, config, "I need a backend engineer")

    state = graph.get_state(config)
    assert state.next == ()
    assert state.values["messages"][-1].content == "Here is a draft."
    assert saved_jobs == []


def test_saving_waits_for_approval_then_runs(monkeypatch, saved_jobs) -> None:
    graph = _graph_with_replies(
        monkeypatch, [_save_call(VALID_ARGS), AIMessage("Saved as HL-BE-01.")]
    )
    config = thread_config("t2")

    _send(graph, config, "I approve")
    paused = graph.get_state(config)
    assert paused.next == ("human_approval",)
    assert saved_jobs == []

    graph.invoke(Command(resume={"approved": True}), config)
    finished = graph.get_state(config)
    assert finished.next == ()
    assert finished.values["saved_job_id"] == 7
    assert finished.values["messages"][-1].content == "Saved as HL-BE-01."
    assert saved_jobs[0]["user_id"] == 1


def test_interviewer_edits_are_used_when_approving(monkeypatch, saved_jobs) -> None:
    graph = _graph_with_replies(
        monkeypatch, [_save_call(VALID_ARGS), AIMessage("Saved.")]
    )
    config = thread_config("t3")
    edited = {**VALID_ARGS, "title": "Senior Backend Engineer"}

    _send(graph, config, "I approve")
    graph.invoke(Command(resume={"approved": True, "arguments": edited}), config)

    assert saved_jobs[0]["arguments"]["title"] == "Senior Backend Engineer"


def test_rejection_returns_to_the_agent_without_saving(monkeypatch, saved_jobs) -> None:
    graph = _graph_with_replies(
        monkeypatch, [_save_call(VALID_ARGS), AIMessage("What should I change?")]
    )
    config = thread_config("t4")

    _send(graph, config, "I approve")
    graph.invoke(
        Command(resume={"approved": False, "feedback": "Add Docker"}), config
    )

    state = graph.get_state(config)
    assert state.next == ()
    assert saved_jobs == []
    assert "Add Docker" in state.values["messages"][-2].content
    assert state.values["messages"][-1].content == "What should I change?"


def test_invalid_details_are_sent_back_for_correction(monkeypatch, saved_jobs) -> None:
    bad_args = {**VALID_ARGS, "scoring_weights": {"technical_skills": 0.9, "experience": 0.9, "qualifications": 0.9}}
    graph = _graph_with_replies(
        monkeypatch,
        [_save_call(bad_args, "c1"), _save_call(VALID_ARGS, "c2"), AIMessage("Saved.")],
    )
    config = thread_config("t5")

    _send(graph, config, "I approve")
    graph.invoke(Command(resume={"approved": True}), config)
    assert graph.get_state(config).next == ("human_approval",)

    graph.invoke(Command(resume={"approved": True}), config)
    state = graph.get_state(config)
    assert state.next == ()
    assert len(saved_jobs) == 1
    assert state.values["attempts"] == 1


def test_repeated_failures_end_with_a_clear_message(monkeypatch, saved_jobs) -> None:
    bad_args = {**VALID_ARGS, "title": "x"}
    graph = _graph_with_replies(
        monkeypatch, [_save_call(bad_args, f"c{i}") for i in range(3)]
    )
    config = thread_config("t6")

    _send(graph, config, "I approve")
    for _ in range(3):
        graph.invoke(Command(resume={"approved": True}), config)

    state = graph.get_state(config)
    assert state.next == ()
    assert saved_jobs == []
    assert state.values["messages"][-1].content == ERROR_REPLY


def test_model_failure_gives_a_clear_message(monkeypatch, saved_jobs) -> None:
    def broken_model():
        raise ConnectionError("no network")

    monkeypatch.setattr(recruiter, "get_agent_model", broken_model)
    monkeypatch.setattr(recruiter, "run_with_retries", lambda operation, call: call())
    graph = recruiter.build_recruiter_graph(InMemorySaver())
    config = thread_config("t7")

    _send(graph, config, "Hello")

    assert graph.get_state(config).values["messages"][-1].content == ERROR_REPLY