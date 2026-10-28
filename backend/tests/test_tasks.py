"""Tests for the parts of the task framework that need no database."""

from datetime import datetime, timezone

from app.core.errors import ServiceUnavailableError
from app.schemas.task import TaskResponse
from app.services.task_service import GENERIC_FAILURE_MESSAGE, safe_error_message


def _task(current: int, total: int) -> TaskResponse:
    return TaskResponse(
        id="abc",
        kind="evaluation",
        status="running",
        progress_current=current,
        progress_total=total,
        message=None,
        result=None,
        error_message=None,
        created_at=datetime.now(timezone.utc),
        started_at=None,
        finished_at=None,
    )


def test_percent_is_calculated_from_progress() -> None:
    assert _task(5, 20).percent == 25
    assert _task(20, 20).percent == 100


def test_percent_is_zero_before_the_total_is_known() -> None:
    assert _task(0, 0).percent == 0


def test_our_own_error_messages_are_shown() -> None:
    error = ServiceUnavailableError("The AI service is not responding.")

    assert safe_error_message(error) == "The AI service is not responding."


def test_unexpected_errors_get_a_generic_message() -> None:
    error = RuntimeError("database password is hunter2")

    assert safe_error_message(error) == GENERIC_FAILURE_MESSAGE