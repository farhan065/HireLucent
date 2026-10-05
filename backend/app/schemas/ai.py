"""Schemas for the AI status check."""

from typing import Literal

from pydantic import BaseModel


class AIModelStatus(BaseModel):
    provider: str
    model: str
    status: Literal["ok", "unavailable"]


class AIStatusResponse(BaseModel):
    llm: AIModelStatus
    embeddings: AIModelStatus