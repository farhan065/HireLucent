"""Tests for the AI access layer. No real AI service is called."""

import pytest
from langchain_core.language_models import FakeListChatModel

from app.ai import client
from app.ai.models import build_rate_limiter
from app.core.errors import ServiceUnavailableError


class FakeEmbeddingModel:
    """Stands in for the real embedding model: 8 zeros for every text."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 8 for _ in texts]


@pytest.fixture(autouse=True)
def waits(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Skip the wait between retries, and record how long each would be."""
    recorded: list[float] = []
    monkeypatch.setattr(client.time, "sleep", recorded.append)
    return recorded


def test_returns_the_result_when_the_call_works() -> None:
    assert client.run_with_retries("test", lambda: "done") == "done"


def test_retries_then_succeeds() -> None:
    attempts = []

    def flaky_call() -> str:
        attempts.append(1)
        if len(attempts) < 3:
            raise TimeoutError("slow")
        return "done"

    assert client.run_with_retries("test", flaky_call) == "done"
    assert len(attempts) == 3


def test_gives_a_clear_error_after_the_last_attempt() -> None:
    attempts = []

    def failing_call() -> str:
        attempts.append(1)
        raise ConnectionError("internal detail that must not reach the user")

    with pytest.raises(ServiceUnavailableError) as error:
        client.run_with_retries("test", failing_call)

    assert len(attempts) == 3
    assert error.value.message == client.AI_UNAVAILABLE_MESSAGE
    assert "internal detail" not in error.value.message


def test_a_caller_can_ask_for_fewer_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client.time, "sleep", lambda seconds: None)
    attempts = []

    def failing_call() -> str:
        attempts.append(1)
        raise ConnectionError("down")

    with pytest.raises(ServiceUnavailableError):
        client.run_with_retries("test", failing_call, max_attempts=2)

    assert len(attempts) == 2


def test_generate_text_returns_the_model_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_model = FakeListChatModel(responses=["Hello from the model"])
    monkeypatch.setattr(client, "get_chat_model", lambda: fake_model)

    assert client.generate_text("Say hello") == "Hello from the model"


def test_embed_texts_returns_one_vector_per_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client, "get_embedding_model", lambda: FakeEmbeddingModel())

    vectors = client.embed_texts(["first", "second"])

    assert len(vectors) == 2
    assert len(vectors[0]) == 8


def test_rate_limit_errors_are_recognised() -> None:
    assert client.is_rate_limit(RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded"))
    assert not client.is_rate_limit(ConnectionError("network unreachable"))


def test_a_rate_limit_waits_longer_before_retrying(waits: list[float]) -> None:
    def limited_call() -> str:
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    with pytest.raises(ServiceUnavailableError):
        client.run_with_retries("test", limited_call)

    assert waits == [client.RATE_LIMIT_WAIT_SECONDS, client.RATE_LIMIT_WAIT_SECONDS]


def test_other_errors_wait_briefly_before_retrying(waits: list[float]) -> None:
    def failing_call() -> str:
        raise ConnectionError("network unreachable")

    with pytest.raises(ServiceUnavailableError):
        client.run_with_retries("test", failing_call)

    assert waits == [2, 4]


def test_calls_are_paced_to_the_per_minute_limit() -> None:
    limiter = build_rate_limiter(requests_per_minute=15)

    assert limiter.requests_per_second == 0.25
    assert limiter.max_bucket_size == 1


class CountingLimiter:
    """Records how many calls waited for the background limiter."""

    def __init__(self) -> None:
        self.waits = 0

    def acquire(self, blocking: bool = True) -> bool:
        self.waits += 1
        return True


@pytest.fixture()
def background_limiter(monkeypatch: pytest.MonkeyPatch) -> CountingLimiter:
    limiter = CountingLimiter()
    monkeypatch.setattr(client, "get_background_rate_limiter", lambda: limiter)
    monkeypatch.setattr(
        client, "get_chat_model", lambda: FakeListChatModel(responses=["ok", "ok"])
    )
    return limiter


def test_interactive_calls_skip_the_background_limiter(
    background_limiter: CountingLimiter,
) -> None:
    assert client.generate_text("hello") == "ok"
    assert background_limiter.waits == 0


def test_background_calls_wait_for_their_own_limiter(
    background_limiter: CountingLimiter,
) -> None:
    with client.background_calls():
        client.generate_text("hello")
    client.generate_text("hello again")

    assert background_limiter.waits == 1


def test_background_mark_reaches_graph_nodes() -> None:
    """Screening runs its CV pipeline inside background_calls(); the mark
    must still be set inside the graph's nodes."""
    from typing import TypedDict

    from langgraph.graph import END, START, StateGraph

    class State(TypedDict, total=False):
        seen: bool

    graph = StateGraph(State)
    graph.add_node("node", lambda state: {"seen": client._background.get()})
    graph.add_edge(START, "node")
    graph.add_edge("node", END)
    pipeline = graph.compile()

    with client.background_calls():
        assert pipeline.invoke({})["seen"] is True
    assert pipeline.invoke({})["seen"] is False
