"""Schemas for the recruiter chatbot."""

from typing import Any, Literal

from pydantic import BaseModel, Field


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


class PendingAction(BaseModel):
    """An action that is waiting for the interviewer's approval."""

    action: str
    arguments: dict[str, Any]


class ChatTurnResponse(BaseModel):
    thread_id: str
    status: Literal["replied", "waiting_for_approval"]
    reply: str
    pending_action: PendingAction | None = None
    job_id: int | None = Field(
        default=None, description="Set once a job has been saved in this chat."
    )



class SocketMessage(BaseModel):
    """What the browser sends over the chat WebSocket."""

    type: Literal["message", "approval"]
    thread_id: str | None = None
    text: str | None = Field(default=None, max_length=4000)
    approved: bool | None = None
    feedback: str | None = Field(default=None, max_length=1000)
    arguments: dict[str, Any] | None = None