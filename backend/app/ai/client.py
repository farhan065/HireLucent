"""AI access layer: the one place the application calls AI models.

Every call has a timeout, is retried a few times, and ends in a clear
ServiceUnavailableError if it still fails. Prompts and answers are never
logged, because they can contain candidate data.
"""

import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TypeVar

from pydantic import BaseModel

from app.ai.models import get_background_rate_limiter, get_chat_model, get_embedding_model
from app.ai.usage import usage_context
from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.core.logging import get_logger, log_event

logger = get_logger(__name__)

T = TypeVar("T")
SchemaT = TypeVar("SchemaT", bound=BaseModel)

AI_UNAVAILABLE_MESSAGE = (
    "The AI service is not responding right now. Please try again in a moment."
)
RETRY_WAIT_SECONDS = 2
# A rate limit resets within a minute, so a short wait would only fail again.
RATE_LIMIT_WAIT_SECONDS = 20

# True while background work (CV screening) is making AI calls.
_background = ContextVar("ai_background", default=False)


@contextmanager
def background_calls() -> Iterator[None]:
    """Mark the AI calls made inside this block as background work.

    They are held to a lower rate than interactive calls, so screening many
    CVs never leaves the AI Agent or the interview room waiting.
    """
    token = _background.set(True)
    try:
        yield
    finally:
        _background.reset(token)


def _wait_turn() -> None:
    """Background calls wait for their own, slower pace first."""
    if _background.get():
        get_background_rate_limiter().acquire()


def is_rate_limit(exc: Exception) -> bool:
    """True if the provider refused the call for sending too many requests."""
    text = f"{type(exc).__name__} {exc}".lower()
    return any(
        marker in text
        for marker in ("429", "resource_exhausted", "resourceexhausted", "ratelimit")
    )


def run_with_retries(
    operation: str, call: Callable[[], T], max_attempts: int | None = None
) -> T:
    """Run one AI call, retrying on failure with a growing wait.

    max_attempts defaults to the AI_MAX_ATTEMPTS setting. Raises
    ServiceUnavailableError when every attempt has failed.
    """
    max_attempts = max_attempts or get_settings().ai_max_attempts
    for attempt in range(1, max_attempts + 1):
        try:
            with usage_context(attempt=attempt):
                return call()
        except Exception as exc:
            rate_limited = is_rate_limit(exc)
            log_event(
                logger,
                "ai_call_failed",
                level=logging.WARNING,
                operation=operation,
                attempt=attempt,
                max_attempts=max_attempts,
                error_type=type(exc).__name__,
                rate_limited=rate_limited,
            )
            if attempt == max_attempts:
                raise ServiceUnavailableError(AI_UNAVAILABLE_MESSAGE) from exc
            time.sleep(
                RATE_LIMIT_WAIT_SECONDS if rate_limited else RETRY_WAIT_SECONDS * attempt
            )
    raise ServiceUnavailableError(AI_UNAVAILABLE_MESSAGE)


def generate_text(prompt: str) -> str:
    """Ask the chat model for a plain-text answer."""

    def call():
        _wait_turn()
        return get_chat_model().invoke(prompt)

    response = run_with_retries("generate_text", call)
    return response.text


def generate_structured(prompt: str, schema: type[SchemaT]) -> SchemaT:
    """Ask the chat model for an answer that matches a Pydantic schema."""
    model = get_chat_model().with_structured_output(schema)

    def call():
        _wait_turn()
        return model.invoke(prompt)

    return run_with_retries("generate_structured", call)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Turn documents into vectors for storing in ChromaDB."""
    return run_with_retries(
        "embed_texts", lambda: get_embedding_model().embed_documents(texts)
    )


def embed_query(text: str) -> list[float]:
    """Turn a search query into a vector."""
    return run_with_retries("embed_query", lambda: get_embedding_model().embed_query(text))
