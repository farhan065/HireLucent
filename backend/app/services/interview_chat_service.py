"""The AI Agent chat in the interview room.

It is the Recruiter Agent in its read-only interview mode: it answers
questions about the job, this candidate and the question bank, and cannot
change anything. Each interview has its own thread, kept by the LangGraph
checkpointer, so the chat comes back after a reload. It is not listed with
the AI Agent's job conversations.
"""

import json

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.core.logging import get_logger, log_event
from app.graphs.base import thread_config
from app.graphs.recruiter.tools import QUESTION_BANK_TOOL
from app.models.enums import SessionStatus
from app.services import session_service

logger = get_logger(__name__)

FINISHED = "This interview has ended or was cancelled."


def thread_id(session_id: int) -> str:
    return f"interview-{session_id}"


def _found_questions(content: str) -> bool:
    """True if a question bank search returned at least one question."""
    try:
        return bool(json.loads(content))
    except (TypeError, ValueError):
        return False


def _view(messages: list[AnyMessage]) -> list[dict]:
    """The chat as the interviewer sees it: their messages and the agent's
    answers, without the tool calls in between. An answer that used
    questions from the question bank is marked."""
    view = []
    tool_names: dict[str, str] = {}
    used_bank = False
    for message in messages:
        if isinstance(message, HumanMessage):
            view.append({"role": "interviewer", "text": message.text})
            used_bank = False
        elif isinstance(message, AIMessage) and message.tool_calls:
            tool_names.update({call["id"]: call["name"] for call in message.tool_calls})
        elif isinstance(message, ToolMessage):
            if tool_names.get(message.tool_call_id) == QUESTION_BANK_TOOL:
                used_bank = used_bank or _found_questions(message.text)
        elif isinstance(message, AIMessage) and message.text.strip():
            view.append(
                {
                    "role": "agent",
                    "text": message.text,
                    "from_question_bank": used_bank,
                    "failed": bool(message.additional_kwargs.get("failed")),
                }
            )
            used_bank = False
    return view


def read(db: Session, graph: CompiledStateGraph, session_id: int) -> list[dict]:
    """The interview's chat so far."""
    session_service.get_session(db, session_id)
    state = graph.get_state(thread_config(thread_id(session_id)))
    return _view(state.values.get("messages", []))


def send(
    db: Session, graph: CompiledStateGraph, session_id: int, user_id: int, text: str
) -> list[dict]:
    """Ask the agent something about this interview and return the chat."""
    session = session_service.get_session(db, session_id)
    if session.status not in (SessionStatus.SCHEDULED, SessionStatus.IN_PROGRESS):
        raise ConflictError(FINISHED)
    config = thread_config(thread_id(session_id))
    graph.invoke(
        {"messages": [HumanMessage(text)], "user_id": user_id, "interview_id": session_id},
        config,
    )
    log_event(logger, "interview_chat_answered", session_id=session_id)
    return _view(graph.get_state(config).values.get("messages", []))
