"""Tests for the AI access layer. No real AI service is called."""

import pytest
from langchain_core.language_models import FakeListChatModel

from app.ai import client
from app.core.errors import ServiceUnavailableError


class FakeEmbeddingModel:
    """Stands in for the real embedding model: 8 zeros for every text."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 8 for _ in texts]


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip the wait between retries so the tests run instantly."""
    monkeypatch.setattr(client.time, "sleep", lambda seconds: None)


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