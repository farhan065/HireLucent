"""Tests for the shared graph building blocks and the demo graph.

They use an in-memory checkpointer, so no database is needed.
"""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.graphs.base import MAX_ATTEMPTS, can_retry, capture_errors, thread_config
from app.graphs.demo import build_demo_graph


def test_capture_errors_stores_the_error_type_only() -> None:
    @capture_errors
    def failing_node(state: dict) -> dict:
        raise ValueError("private detail")

    assert failing_node({}) == {"error": "ValueError"}


def test_can_retry_until_the_limit() -> None:
    assert can_retry({"attempts": MAX_ATTEMPTS - 1})
    assert not can_retry({"attempts": MAX_ATTEMPTS})


def test_graph_pauses_for_approval_then_resumes() -> None:
    graph = build_demo_graph(InMemorySaver())
    config = thread_config("run-1")

    graph.invoke({"text": "Backend Engineer"}, config)
    paused = graph.get_state(config)
    assert paused.next == ("human_approval",)
    assert paused.values["draft"] == "Draft: Backend Engineer"

    graph.invoke(Command(resume=True), config)
    finished = graph.get_state(config)
    assert finished.next == ()
    assert finished.values["result"] == "approved"


def test_rejection_is_recorded() -> None:
    graph = build_demo_graph(InMemorySaver())
    config = thread_config("run-2")

    graph.invoke({"text": "Backend Engineer"}, config)
    graph.invoke(Command(resume=False), config)

    assert graph.get_state(config).values["result"] == "rejected"


def test_failing_node_follows_the_error_path() -> None:
    graph = build_demo_graph(InMemorySaver())
    config = thread_config("run-3")

    graph.invoke({"text": "   "}, config)
    state = graph.get_state(config)

    assert state.next == ()
    assert state.values["error"] == "ValueError"
    assert state.values["result"] == "failed"


def test_runs_are_kept_separate() -> None:
    graph = build_demo_graph(InMemorySaver())

    graph.invoke({"text": "first"}, thread_config("a"))
    graph.invoke({"text": "second"}, thread_config("b"))

    assert graph.get_state(thread_config("a")).values["draft"] == "Draft: first"
    assert graph.get_state(thread_config("b")).values["draft"] == "Draft: second"