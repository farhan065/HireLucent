"""Recruiter chatbot endpoints."""

from fastapi import APIRouter, Depends
from langgraph.graph.state import CompiledStateGraph

from app.api.deps import Principal, require_interviewer
from app.graphs.recruiter.graph import get_recruiter_graph
from app.schemas.chat import ApprovalRequest, ChatMessageRequest, ChatTurnResponse
from app.schemas.error import ErrorResponse
from app.services import chat_service

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post(
    "/messages",
    response_model=ChatTurnResponse,
    summary="Send a message to the recruiting assistant",
    responses={503: {"model": ErrorResponse, "description": "AI unavailable"}},
)
def send_message(
    payload: ChatMessageRequest,
    principal: Principal = Depends(require_interviewer),
    graph: CompiledStateGraph = Depends(get_recruiter_graph),
) -> ChatTurnResponse:
    """Start a conversation, or continue one by giving its thread_id."""
    return chat_service.send_message(
        graph, principal.subject_id, payload.thread_id, payload.message
    )


@router.post(
    "/{thread_id}/approval",
    response_model=ChatTurnResponse,
    summary="Approve or reject the action the assistant is waiting on",
    responses={
        404: {"model": ErrorResponse, "description": "Conversation not found"},
        409: {"model": ErrorResponse, "description": "Nothing to approve"},
    },
)
def submit_approval(
    thread_id: str,
    payload: ApprovalRequest,
    principal: Principal = Depends(require_interviewer),
    graph: CompiledStateGraph = Depends(get_recruiter_graph),
) -> ChatTurnResponse:
    return chat_service.submit_approval(
        graph,
        principal.subject_id,
        thread_id,
        payload.approved,
        payload.feedback,
        payload.arguments,
    )