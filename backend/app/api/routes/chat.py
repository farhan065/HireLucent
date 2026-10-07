"""AI Agent endpoints (the non-streaming API)."""

from fastapi import APIRouter, Depends, status
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_interviewer
from app.db.session import get_db
from app.graphs.recruiter.graph import get_recruiter_graph
from app.models import Conversation
from app.schemas.chat import (
    ApprovalRequest,
    ChatMessageRequest,
    ConversationSummary,
    ConversationView,
    DescriptionEditRequest,
)
from app.schemas.error import ErrorResponse
from app.services import chat_service, conversation_store, job_deletion

router = APIRouter(prefix="/chat", tags=["Chat"])

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Conversation not found"}}
CONFLICT = {409: {"model": ErrorResponse, "description": "Not possible right now"}}


@router.get(
    "/conversations",
    response_model=list[ConversationSummary],
    summary="List the interviewer's conversations",
)
def list_conversations(
    principal: Principal = Depends(require_interviewer),
) -> list[Conversation]:
    """Most recently used first. There is one conversation per job."""
    return conversation_store.list_summaries(principal.subject_id)


@router.delete(
    "/conversations/{thread_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation that has not saved a job yet",
    responses={**NOT_FOUND, **CONFLICT},
)
def delete_conversation(
    thread_id: str,
    principal: Principal = Depends(require_interviewer),
    db: Session = Depends(get_db),
) -> None:
    """For a job that is still being drafted. A saved job is deleted with
    DELETE /jobs/{id}, which removes its conversation too."""
    job_deletion.delete_draft(db, principal.subject_id, thread_id)


@router.post(
    "/messages",
    response_model=ConversationView,
    summary="Send a message to the AI Agent",
    responses={503: {"model": ErrorResponse, "description": "AI unavailable"}},
)
def send_message(
    payload: ChatMessageRequest,
    principal: Principal = Depends(require_interviewer),
    graph: CompiledStateGraph = Depends(get_recruiter_graph),
) -> ConversationView:
    """Start a conversation, or continue one by giving its thread_id."""
    return chat_service.send_message(
        graph, principal.subject_id, payload.thread_id, payload.message
    )


@router.get(
    "/{thread_id}",
    response_model=ConversationView,
    summary="Open a conversation with its full history",
    responses=NOT_FOUND,
)
def read_conversation(
    thread_id: str,
    principal: Principal = Depends(require_interviewer),
    graph: CompiledStateGraph = Depends(get_recruiter_graph),
) -> ConversationView:
    return chat_service.get_conversation(graph, principal.subject_id, thread_id)


@router.post(
    "/{thread_id}/approval",
    response_model=ConversationView,
    summary="Confirm or reject what the assistant is waiting on",
    responses={**NOT_FOUND, **CONFLICT},
)
def submit_approval(
    thread_id: str,
    payload: ApprovalRequest,
    principal: Principal = Depends(require_interviewer),
    graph: CompiledStateGraph = Depends(get_recruiter_graph),
) -> ConversationView:
    return chat_service.submit_approval(
        graph,
        principal.subject_id,
        thread_id,
        payload.approved,
        payload.feedback,
        payload.arguments,
    )


@router.put(
    "/{thread_id}/description",
    response_model=ConversationView,
    summary="Save a job description edited directly by the interviewer",
    responses={**NOT_FOUND, **CONFLICT},
)
def edit_description(
    thread_id: str,
    payload: DescriptionEditRequest,
    principal: Principal = Depends(require_interviewer),
    graph: CompiledStateGraph = Depends(get_recruiter_graph),
) -> ConversationView:
    """The edited text becomes the newest draft and still needs approval."""
    return chat_service.edit_description(
        graph, principal.subject_id, thread_id, payload.title, payload.text
    )
