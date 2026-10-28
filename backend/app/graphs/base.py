"""Shared building blocks for every LangGraph workflow in HireLucent."""

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, TypedDict

from app.core.logging import get_logger, log_event

logger = get_logger(__name__)

# How many times a node may be repeated, for example when the AI returns
# output that does not pass validation.
MAX_ATTEMPTS = 3


class BaseState(TypedDict, total=False):
    """Fields every graph's state has. Each graph adds its own fields."""

    error: str | None
    attempts: int


def capture_errors(node: Callable[[Any], dict]) -> Callable[[Any], dict]:
    """Wrap a node so a failure is stored in the state instead of crashing.

    The graph can then follow its error path (see route_on_error). Only the
    error type is stored and logged, never the message, which may contain
    candidate data.
    """

    @wraps(node)
    def wrapper(state: Any) -> dict:
        try:
            return node(state)
        except Exception as exc:
            error_type = type(exc).__name__
            log_event(
                logger,
                "graph_node_failed",
                level=logging.ERROR,
                node=node.__name__,
                error_type=error_type,
            )
            return {"error": error_type}

    return wrapper


def route_on_error(next_node: str, error_node: str) -> Callable[[Any], str]:
    """Build a router: go to error_node if the state holds an error."""

    def router(state: Any) -> str:
        return error_node if state.get("error") else next_node

    return router


def can_retry(state: Any) -> bool:
    """True while a node has attempts left."""
    return state.get("attempts", 0) < MAX_ATTEMPTS


def thread_config(thread_id: str) -> dict:
    """The config LangGraph needs to save and find one run of a graph."""
    return {"configurable": {"thread_id": thread_id}}