"""Schemas for the health endpoint."""

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response body of GET /health."""

    status: Literal["ok"] = Field(description="Service status.")
    service: str = Field(description="Service name.")
    version: str = Field(description="Application version.")
    environment: str = Field(description="Runtime environment.")