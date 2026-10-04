"""Schemas for the uniform error response."""

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """One field-level problem in a request."""

    field: str = Field(description="Location of the invalid value, e.g. body.email.")
    message: str = Field(description="What is wrong with the value.")


class ErrorBody(BaseModel):
    """Error information returned to the client."""

    code: str = Field(description="Stable machine-readable error code.")
    message: str = Field(description="Message suitable for showing to a user.")
    request_id: str | None = Field(
        default=None, description="Identifier to quote when reporting the problem."
    )
    details: list[ErrorDetail] = Field(
        default_factory=list, description="Field-level problems, if any."
    )


class ErrorResponse(BaseModel):
    """Envelope used by every error response."""

    error: ErrorBody