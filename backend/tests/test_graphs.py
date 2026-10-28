"""Tests for the shared graph building blocks used by every LangGraph."""

from app.graphs.base import MAX_ATTEMPTS, can_retry, capture_errors, thread_config


def test_capture_errors_stores_the_error_type_only() -> None:
    @capture_errors
    def failing_node(state: dict) -> dict:
        raise ValueError("private detail")

    assert failing_node({}) == {"error": "ValueError"}


def test_can_retry_until_the_limit() -> None:
    assert can_retry({"attempts": MAX_ATTEMPTS - 1})
    assert not can_retry({"attempts": MAX_ATTEMPTS})


def test_each_run_gets_its_own_thread() -> None:
    assert thread_config("a") != thread_config("b")
    assert thread_config("a")["configurable"]["thread_id"] == "a"
