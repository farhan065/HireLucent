"""Request context middleware: request ID, request logging, last-resort errors."""

import logging
import time
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.ai.usage import route_label, usage_context
from app.core.errors import internal_error_response, log_unhandled_exception
from app.core.logging import get_logger, log_event, request_id_ctx

logger = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"

# Paths polled by container health checks. Logging them would flood the logs.
QUIET_PATHS = frozenset({"/health"})


class RequestContextMiddleware:
    """Give each HTTP request an ID, log it, and catch unexpected errors.

    The ID is added to every log line written during the request and returned
    in the X-Request-ID response header. Only the method, path, status and
    duration are logged. Query strings, headers and bodies are never logged.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid4().hex
        token = request_id_ctx.set(request_id)
        started_at = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            # AI calls made for this request, including its background work,
            # are counted under its route in the AI cost report.
            with usage_context(route=route_label(scope["method"], scope["path"])):
                await self.app(scope, receive, send_with_request_id)
        except Exception as exc:
            log_unhandled_exception(exc)
            if response_started:
                raise
            response = internal_error_response()
            await response(scope, receive, send_with_request_id)
        finally:
            if scope["path"] not in QUIET_PATHS:
                log_event(
                    logger,
                    "request_completed",
                    level=logging.INFO,
                    method=scope["method"],
                    path=scope["path"],
                    status_code=status_code,
                    duration_ms=round((time.perf_counter() - started_at) * 1000, 1),
                )
            request_id_ctx.reset(token)