"""Structured JSON logging.

Every log line is one JSON object with: time, level, service, request_id,
event and fields. Log identifiers only. Never log names, emails, CV text,
transcripts, tokens, keys or prompts.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.core.config import Settings

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def __init__(self, service: str) -> None:
        super().__init__()
        self._service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "service": self._service,
            "request_id": request_id_ctx.get(),
            "event": record.getMessage(),
            "fields": getattr(record, "fields", {}),
        }
        return json.dumps(payload, default=str)


def configure_logging(settings: Settings) -> None:
    """Send all logs to stdout and to a rotating file, as JSON lines."""
    formatter = JsonFormatter(service=settings.log_service_name)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    handlers: list[logging.Handler] = [stream_handler]

    file_error: str | None = None
    try:
        log_dir = Path(settings.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / settings.log_file_name,
            maxBytes=settings.log_file_max_bytes,
            backupCount=settings.log_file_backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    except OSError as exc:
        file_error = type(exc).__name__

    root = logging.getLogger()
    root.handlers = handlers
    root.setLevel(settings.log_level)

    # Uvicorn: reuse our handlers, and drop its access log. Request logging is
    # done by the request context middleware, without query strings.
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True

    # HTTP client libraries log full request URLs at INFO level. URLs can carry
    # API keys or tokens in the query string, so only warnings are kept.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)

    if file_error is not None:
        log_event(
            logging.getLogger(__name__),
            "log_file_unavailable",
            level=logging.WARNING,
            error_type=file_error,
        )


def get_logger(name: str) -> logging.Logger:
    """Return a logger for the given module name."""
    return logging.getLogger(name)


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    """Log one event with structured fields.

    Pass identifiers and counts only, for example candidate_id=12.
    """
    logger.log(level, event, extra={"fields": fields})