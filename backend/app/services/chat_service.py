"""ChatService: runs the Recruiter Agent for one conversation.

Each conversation is one LangGraph thread and belongs to one job. Its
messages and any pending approval are saved in the checkpoints, so a
conversation can be reopened later, even after a restart.
"""

import re
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessageChunk, HumanMessage
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger, log_event
from app.graphs.base import thread_config
from app.graphs.recruiter.drafts import EDIT_KIND
from app.schemas.chat import ConversationView
from app.services import conversation_store
from app.services.conversation_view import build_view

logger = get_logger(__name__)

# A short message that only agrees, such as "yes" or "looks good, save it".
_CLEAR_YES = re.compile(
    r"^\W*(yes|ok|okay|confirm|confirmed|approve|approved|looks good|save it|save)"
    r"\b[\w\s,.!]{0,30}$",
    re.IGNORECASE,
)
_CHANGE_WORDS = re.compile(r"\b(but|change|add|remove|not|no|don't|instead)\b", re.I)


def is_clear_yes(text: str) -> bool:
    """True if the message agrees and asks for nothing else."""
    return bool(_CLEAR_YES.match(text)) and not _CHANGE_WORDS.search(text)


def get_conversation(
    graph: CompiledStateGraph, user_id: int, thread_id: str
) -> ConversationView:
    """Reopen a conversation with its full history."""
    _check_owner(graph, user_id, thread_id)
    return _view(graph, thread_id)


def send_message(
    graph: CompiledStateGraph, user_id: int, thread_id: str | None, text: str
) -> ConversationView:
    """Give the interviewer's message to the agent and return the result."""
    thread_id, turn_input = _prepare_turn(graph, user_id, thread_id, text)
    graph.invoke(turn_input, thread_config(thread_id))
    return _finish_turn(graph, user_id, thread_id)


def stream_message(
    graph: CompiledStateGraph, user_id: int, thread_id: str | None, text: str
) -> Iterator[dict[str, Any]]:
    """Like send_message, but yields the reply piece by piece as it is written.

    Yields {"type": "token", "text": ...} for each piece, then one
    {"type": "view", ...} event with the complete conversation.
    """
    thread_id, turn_input = _prepare_turn(graph, user_id, thread_id, text)
    yield from _stream_turn(graph, user_id, thread_id, turn_input)


def submit_approval(
    graph: CompiledStateGraph,
    user_id: int,
    thread_id: str,
    approved: bool,
    feedback: str | None,
    arguments: dict | None,
) -> ConversationView:
    """Continue a paused conversation with the interviewer's decision."""
    decision = _prepare_approval(
        graph, user_id, thread_id, approved, feedback, arguments
    )
    graph.invoke(decision, thread_config(thread_id))
    return _finish_turn(graph, user_id, thread_id)


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
    yield from _stream_turn(graph, user_id, thread_id, decision)


def edit_description(
    graph: CompiledStateGraph, user_id: int, thread_id: str, title: str, text: str
) -> ConversationView:
    """Store a description the interviewer edited directly.

    It becomes the newest draft and still needs approval. No AI call is made.
    """
    _check_owner(graph, user_id, thread_id)
    snapshot = graph.get_state(thread_config(thread_id))
    if snapshot.values.get("saved_job_id"):
        raise ConflictError("This job is already saved.")
    if snapshot.next:
        raise ConflictError(
            "Confirm or change the requirements first, then edit the description."
        )

    edit = HumanMessage(
        content=f"# {title.strip()}\n\n{text.strip()}",
        additional_kwargs={"kind": EDIT_KIND},
    )
    # Recorded as the output of the last node, so the turn stays finished.
    graph.update_state(
        thread_config(thread_id), {"messages": [edit]}, as_node="respond"
    )
    log_event(logger, "chat_description_edited", thread_id=thread_id, user_id=user_id)
    return _finish_turn(graph, user_id, thread_id)


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
        # While an approval is pending, a clear yes approves it. Anything
        # else counts as "not approved, here is what to change".
        if is_clear_yes(text):
            return thread_id, Command(resume={"approved": True})
        return thread_id, Command(resume={"approved": False, "feedback": text})
    return thread_id, {"messages": [HumanMessage(text)], "user_id": user_id}


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


def _stream_turn(
    graph: CompiledStateGraph, user_id: int, thread_id: str, turn_input: Any
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
    view = _finish_turn(graph, user_id, thread_id)
    yield {"type": "view", **view.model_dump()}


def _finish_turn(
    graph: CompiledStateGraph, user_id: int, thread_id: str
) -> ConversationView:
    """Build the view after a turn and update the conversation's summary."""
    view = _view(graph, thread_id)
    conversation_store.save_summary(user_id, view)
    return view


def _view(graph: CompiledStateGraph, thread_id: str) -> ConversationView:
    snapshot = graph.get_state(thread_config(thread_id))
    job_code = conversation_store.job_code_for(snapshot.values.get("saved_job_id"))
    pending = snapshot.tasks[0].interrupts[0].value if snapshot.next else None
    view = build_view(thread_id, snapshot.values, pending, job_code)
    profile = conversation_store.job_profile_for(snapshot.values.get("saved_job_id"))
    if profile is not None:
        view.brief.requirements, view.brief.scoring_weights = profile
        view.brief.requirements_status = "confirmed"
    return view


def _is_waiting(graph: CompiledStateGraph, thread_id: str) -> bool:
    return bool(graph.get_state(thread_config(thread_id)).next)


def _check_owner(graph: CompiledStateGraph, user_id: int, thread_id: str) -> None:
    """A conversation can only be used by the interviewer who started it."""
    values = graph.get_state(thread_config(thread_id)).values
    if not values or values.get("user_id") != user_id:
        raise NotFoundError("This conversation does not exist.")
