"""Schemas for the Hiring Assistant conversation."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Stage = Literal[
    "describing", "reviewing_description", "confirming_requirements", "saved"
]


class TimelineItem(BaseModel):
    """One entry in the conversation, in the order it happened."""

    id: str
    kind: Literal["user", "assistant", "note", "description", "requirements"]
    # user, assistant and note: the text. description: the body in Markdown.
    text: str = ""
    # description only
    title: str | None = None
    version: int | None = None
    # description only: a Knowledge Base template was used to write it.
    from_knowledge_base: bool = False
    # description: waiting, replaced or approved.
    # requirements: waiting, changed or approved.
    status: str | None = None
    # requirements only: the requirements and scoring weights.
    arguments: dict[str, Any] | None = None


class DescriptionBrief(BaseModel):
    version: int
    title: str
    text: str
    status: str


class JobBrief(BaseModel):
    """The current state of the job, shown beside the conversation."""

    description: DescriptionBrief | None = None
    requirements: dict[str, Any] | None = None
    scoring_weights: dict[str, float] | None = None
    requirements_status: Literal["proposed", "confirmed"] | None = None
    job_id: int | None = None
    job_code: str | None = None


class ConversationView(BaseModel):
    """Everything the screen needs to draw one conversation."""

    thread_id: str
    title: str
    stage: Stage
    items: list[TimelineItem]
    brief: JobBrief


class ConversationSummary(BaseModel):
    """A conversation as shown in the job switcher and on the dashboard."""

    model_config = ConfigDict(from_attributes=True)

    thread_id: str
    title: str
    stage: str
    job_id: int | None
    updated_at: datetime


class ChatMessageRequest(BaseModel):
    thread_id: str | None = Field(
        default=None, description="Leave empty to start a new conversation."
    )
    message: str = Field(min_length=1, max_length=4000)


class ApprovalRequest(BaseModel):
    approved: bool
    feedback: str | None = Field(
        default=None, max_length=1000, description="Why it was not approved."
    )
    arguments: dict[str, Any] | None = Field(
        default=None, description="The details as edited by the interviewer."
    )


class DescriptionEditRequest(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    text: str = Field(min_length=50, max_length=20000)


class SocketMessage(BaseModel):
    """What the browser sends over the chat WebSocket."""

    type: Literal["message", "approval", "edit_description"]
    thread_id: str | None = None
    text: str | None = Field(default=None, max_length=20000)
    title: str | None = Field(default=None, max_length=255)
    approved: bool | None = None
    feedback: str | None = Field(default=None, max_length=1000)
    arguments: dict[str, Any] | None = None
