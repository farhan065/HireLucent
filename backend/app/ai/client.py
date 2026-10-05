"""AI access layer: the one place the application calls AI models.

Every call has a timeout, is retried a few times, and ends in a clear
ServiceUnavailableError if it still fails. Prompts and answers are never
logged, because they can contain candidate data.
"""

import logging
import time
from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel

from app.ai.models import get_chat_model, get_embedding_model
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


def run_with_retries(operation: str, call: Callable[[], T]) -> T:
    """Run one AI call, retrying on failure with a growing wait.

    Raises ServiceUnavailableError when every attempt has failed.
    """
    max_attempts = get_settings().ai_max_attempts
    for attempt in range(1, max_attempts + 1):
        try:
            return call()
        except Exception as exc:
            log_event(
                logger,
                "ai_call_failed",
                level=logging.WARNING,
                operation=operation,
                attempt=attempt,
                max_attempts=max_attempts,
                error_type=type(exc).__name__,
            )
            if attempt == max_attempts:
                raise ServiceUnavailableError(AI_UNAVAILABLE_MESSAGE) from exc
            time.sleep(RETRY_WAIT_SECONDS * attempt)
    raise ServiceUnavailableError(AI_UNAVAILABLE_MESSAGE)


def generate_text(prompt: str) -> str:
    """Ask the chat model for a plain-text answer."""
    response = run_with_retries("generate_text", lambda: get_chat_model().invoke(prompt))
    return response.text


def generate_structured(prompt: str, schema: type[SchemaT]) -> SchemaT:
    """Ask the chat model for an answer that matches a Pydantic schema."""
    model = get_chat_model().with_structured_output(schema)
    return run_with_retries("generate_structured", lambda: model.invoke(prompt))


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Turn documents into vectors for storing in ChromaDB."""
    return run_with_retries(
        "embed_texts", lambda: get_embedding_model().embed_documents(texts)
    )


def embed_query(text: str) -> list[float]:
    """Turn a search query into a vector."""
    return run_with_retries("embed_query", lambda: get_embedding_model().embed_query(text))