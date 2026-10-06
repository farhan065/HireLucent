"""ChatService: runs the Recruiter Agent for one conversation.

Each conversation is one LangGraph thread. Its messages and any pending
approval are saved in the checkpoints, so a conversation can be continued
later, even after a restart.
"""

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger, log_event
from app.graphs.base import thread_config
from app.graphs.recruiter.prompts import APPROVAL_PROMPT
from app.schemas.chat import ChatTurnResponse, PendingAction

logger = get_logger(__name__)


def send_message(
    graph: CompiledStateGraph, user_id: int, thread_id: str | None, text: str
) -> ChatTurnResponse:
    """Give the interviewer's message to the agent and return its reply."""
    thread_id, turn_input = _prepare_turn(graph, user_id, thread_id, text)
    graph.invoke(turn_input, thread_config(thread_id))
    return _describe(graph, thread_id)


def stream_message(
    graph: CompiledStateGraph, user_id: int, thread_id: str | None, text: str
) -> Iterator[dict[str, Any]]:
    """Like send_message, but yields the reply piece by piece as it is written.

    Yields {"type": "token", "text": ...} for each piece, then one
    {"type": "turn", ...} event with the complete result.
    """
    thread_id, turn_input = _prepare_turn(graph, user_id, thread_id, text)
    yield from _stream_turn(graph, thread_id, turn_input)


def _prepare_turn(
    graph: CompiledStateGraph, user_id: int, thread_id: str | None, text: str
) -> tuple[str, Any]:
    """Find or start the conversation and build what the graph should receive."""
    if thread_id is None:
        thread_id = uuid4().hex
        log_event(logger, "chat_started", thread_id=thread_id, user_id=user_id)
    else:
        _check_owner(graph, user_id, thread_id)

    if _is_waiting(graph, thread_id):
        # A new message while an approval is pending counts as "not approved,
        # here is what to change".
        return thread_id, Command(resume={"approved": False, "feedback": text})
    return thread_id, {"messages": [HumanMessage(text)], "user_id": user_id}


def _stream_turn(
    graph: CompiledStateGraph, thread_id: str, turn_input: Any
) -> Iterator[dict[str, Any]]:
    """Run one turn, passing on the words the model writes in the agent node."""
    stream = graph.stream(turn_input, thread_config(thread_id), stream_mode="messages")
    for chunk, metadata in stream:
        is_model_text = (
            isinstance(chunk, AIMessageChunk)
            and metadata.get("langgraph_node") == "agent"
            and chunk.text
        )
        if is_model_text:
            yield {"type": "token", "text": chunk.text}
    yield {"type": "turn", **_describe(graph, thread_id).model_dump()}


def submit_approval(
    graph: CompiledStateGraph,
    user_id: int,
    thread_id: str,
    approved: bool,
    feedback: str | None,
    arguments: dict | None,
) -> ChatTurnResponse:
    """Continue a paused conversation with the interviewer's decision."""
    decision = _prepare_approval(
        graph, user_id, thread_id, approved, feedback, arguments
    )
    graph.invoke(decision, thread_config(thread_id))
    return _describe(graph, thread_id)


def stream_approval(
    graph: CompiledStateGraph,
    user_id: int,
    thread_id: str,
    approved: bool,
    feedback: str | None,
    arguments: dict | None,
) -> Iterator[dict[str, Any]]:
    """Like submit_approval, but yields the reply piece by piece."""
    decision = _prepare_approval(
        graph, user_id, thread_id, approved, feedback, arguments
    )
    yield from _stream_turn(graph, thread_id, decision)


def _prepare_approval(
    graph: CompiledStateGraph,
    user_id: int,
    thread_id: str,
    approved: bool,
    feedback: str | None,
    arguments: dict | None,
) -> Command:
    """Check that an approval is expected and build the resume command."""
    _check_owner(graph, user_id, thread_id)
    if not _is_waiting(graph, thread_id):
        raise ConflictError("Nothing is waiting for approval in this conversation.")
    log_event(
        logger, "chat_approval", thread_id=thread_id, user_id=user_id, approved=approved
    )
    return Command(
        resume={"approved": approved, "feedback": feedback, "arguments": arguments}
    )


def _is_waiting(graph: CompiledStateGraph, thread_id: str) -> bool:
    return bool(graph.get_state(thread_config(thread_id)).next)


def _check_owner(graph: CompiledStateGraph, user_id: int, thread_id: str) -> None:
    """A conversation can only be continued by the interviewer who started it."""
    values = graph.get_state(thread_config(thread_id)).values
    if not values or values.get("user_id") != user_id:
        raise NotFoundError("This conversation does not exist.")


def _describe(graph: CompiledStateGraph, thread_id: str) -> ChatTurnResponse:
    """Build the response from the saved state of the conversation."""
    snapshot = graph.get_state(thread_config(thread_id))
    job_id = snapshot.values.get("saved_job_id")

    if snapshot.next:
        pending = snapshot.tasks[0].interrupts[0].value
        return ChatTurnResponse(
            thread_id=thread_id,
            status="waiting_for_approval",
            reply=APPROVAL_PROMPT,
            pending_action=PendingAction(**pending),
            job_id=job_id,
        )

    last = snapshot.values["messages"][-1]
    reply = last.text if isinstance(last, AIMessage) else ""
    return ChatTurnResponse(
        thread_id=thread_id, status="replied", reply=reply, job_id=job_id
    )