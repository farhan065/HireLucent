"""Schemas for the demo graph endpoints."""

from typing import Literal

from pydantic import BaseModel, Field


class DemoStartRequest(BaseModel):
    text: str = Field(max_length=200)


class DemoResumeRequest(BaseModel):
    approved: bool


class DemoRunResponse(BaseModel):
    thread_id: str
    status: Literal["waiting_for_approval", "finished"]
    draft: str | None = None
    result: str | None = None