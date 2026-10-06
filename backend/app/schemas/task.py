"""Schemas for background tasks."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    status: str
    progress_current: int
    progress_total: int
    message: str | None
    result: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @computed_field
    @property
    def percent(self) -> int:
        """Progress from 0 to 100, for a progress bar."""
        if self.progress_total <= 0:
            return 0
        return min(100, round(100 * self.progress_current / self.progress_total))


class DemoTaskRequest(BaseModel):
    steps: int = Field(default=5, ge=1, le=20)
    fail_at: int | None = Field(
        default=None, ge=1, description="Step at which the task should fail."
    )