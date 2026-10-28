"""Uniform error handling.

Every error response has the same shape (see app.schemas.error) and never
contains stack traces, file paths, configuration or prompt content.
"""

import logging
import traceback
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger, log_event, request_id_ctx
from app.schemas.error import ErrorBody, ErrorDetail, ErrorResponse

logger = get_logger(__name__)

INTERNAL_ERROR_MESSAGE = "Something went wrong on our side. Please try again."
VALIDATION_ERROR_MESSAGE = "Some of the information sent is not valid."


class AppError(Exception):
    """Base class for errors raised on purpose by the application."""

    status_code: int = HTTPStatus.BAD_REQUEST
    code: str = "bad_request"

    def __init__(self, message: str, details: list[ErrorDetail] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []


class NotFoundError(AppError):
    status_code = HTTPStatus.NOT_FOUND
    code = "not_found"


class ConflictError(AppError):
    status_code = HTTPStatus.CONFLICT
    code = "conflict"


class UnauthorizedError(AppError):
    status_code = HTTPStatus.UNAUTHORIZED
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = HTTPStatus.FORBIDDEN
    code = "forbidden"


class ServiceUnavailableError(AppError):
    """An external service (LLM, embeddings, Google API) could not be used."""

    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    code = "service_unavailable"


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[ErrorDetail] | None = None,
) -> JSONResponse:
    """Build the uniform error response."""
    body = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            request_id=request_id_ctx.get(),
            details=details or [],
        )
    )
    return JSONResponse(status_code=int(status_code), content=body.model_dump())


def internal_error_response() -> JSONResponse:
    """Build the generic 500 response. It reveals nothing about the cause."""
    return error_response(
        HTTPStatus.INTERNAL_SERVER_ERROR, "internal_error", INTERNAL_ERROR_MESSAGE
    )


def log_unhandled_exception(exc: BaseException) -> None:
    """Log where an unexpected error happened, without its message.

    Exception messages can contain user data (for example a rejected database
    value), so only the error type and the code locations are logged.
    """
    frames = traceback.extract_tb(exc.__traceback__)
    log_event(
        logger,
        "unhandled_exception",
        level=logging.ERROR,
        error_type=type(exc).__name__,
        trace=[f"{frame.filename}:{frame.lineno} in {frame.name}" for frame in frames],
    )


async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    log_event(
        logger,
        "app_error",
        level=logging.WARNING,
        code=exc.code,
        status_code=int(exc.status_code),
    )
    return error_response(exc.status_code, exc.code, exc.message, exc.details)


async def _handle_validation_error(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    # Only the location and the rule are returned. The rejected input value is
    # never echoed back or logged, because it may be personal data.
    details = [
        ErrorDetail(
            field=".".join(str(part) for part in error["loc"]),
            message=error["msg"],
        )
        for error in exc.errors()
    ]
    log_event(
        logger,
        "request_validation_failed",
        level=logging.WARNING,
        fields_invalid=[detail.field for detail in details],
    )
    return error_response(
        HTTPStatus.UNPROCESSABLE_ENTITY,
        "validation_error",
        VALIDATION_ERROR_MESSAGE,
        details,
    )


async def _handle_http_exception(
    _: Request, exc: StarletteHTTPException
) -> JSONResponse:
    try:
        status = HTTPStatus(exc.status_code)
        code, message = status.name.lower(), status.phrase
    except ValueError:
        code, message = "http_error", "Request failed."
    return error_response(exc.status_code, code, message)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the uniform error handlers to the application."""
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)