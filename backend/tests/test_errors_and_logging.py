"""Tests for uniform error responses and structured logging."""

import json
import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.core.errors import NotFoundError
from app.core.logging import JsonFormatter, log_event
from app.main import create_app


SECRET_VALUE = "very-private-value"


class _SamplePayload(BaseModel):
    job_code: str = Field(min_length=30)
    years: int = Field(ge=0)


@pytest.fixture()
def client() -> TestClient:
    app = create_app()

    @app.post("/_test/validate")
    def _validate(payload: _SamplePayload) -> dict[str, bool]:
        return {"ok": True}

    @app.get("/_test/missing")
    def _missing() -> None:
        raise NotFoundError("Candidate not found.")

    @app.get("/_test/crash")
    def _crash() -> None:
        raise RuntimeError(f"database rejected {SECRET_VALUE}")

    return TestClient(app, raise_server_exceptions=False)


def test_unknown_path_uses_uniform_error(client: TestClient) -> None:
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["request_id"] == response.headers["X-Request-ID"]


def test_app_error_uses_uniform_error(client: TestClient) -> None:
    response = client.get("/_test/missing")

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Candidate not found."


def test_validation_error_lists_fields_without_echoing_input(
    client: TestClient,
) -> None:
    response = client.post(
        "/_test/validate", json={"job_code": SECRET_VALUE, "years": -1}
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert {detail["field"] for detail in error["details"]} == {
        "body.job_code",
        "body.years",
    }
    assert SECRET_VALUE not in response.text


def test_unhandled_error_hides_internals(client: TestClient) -> None:
    response = client.get("/_test/crash")

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "internal_error"
    assert "X-Request-ID" in response.headers
    assert SECRET_VALUE not in response.text
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text


def test_unhandled_error_log_has_no_exception_message(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR):
        client.get("/_test/crash")

    records = [r for r in caplog.records if r.getMessage() == "unhandled_exception"]
    assert len(records) == 1
    assert records[0].fields["error_type"] == "RuntimeError"
    assert SECRET_VALUE not in json.dumps(records[0].fields)


def test_log_line_is_json_with_required_keys() -> None:
    logger = logging.getLogger("test.json")
    record_holder: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            record_holder.append(record)

    handler = _Capture()
    logger.addHandler(handler)
    try:
        log_event(logger, "cv_batch_finished", job_id=3, duration_s=41.2)
    finally:
        logger.removeHandler(handler)

    line = JsonFormatter(service="backend").format(record_holder[0])
    payload = json.loads(line)
    assert set(payload) == {
        "time",
        "level",
        "service",
        "request_id",
        "event",
        "fields",
    }
    assert payload["event"] == "cv_batch_finished"
    assert payload["fields"] == {"job_id": 3, "duration_s": 41.2}