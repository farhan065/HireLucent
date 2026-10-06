"""LangGraph 1: the Recruiter Agent.

    start -> load_context -> agent
    agent -> respond              (a plain answer)
    agent -> call_tools           (a read-only tool)
    agent -> human_approval       (an action that needs approval)
    human_approval -> call_tools  (approved)
    human_approval -> agent       (rejected, with feedback)
    call_tools -> agent           (tool result)
    call_tools -> handle_error    (too many failed attempts)
    handle_error -> respond -> end
"""

import logging
from functools import lru_cache
from typing import Annotated, Literal

from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage, AnyMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, interrupt
from pydantic import ValidationError

from app.ai.client import run_with_retries
from app.ai.models import get_chat_model
from app.core.errors import AppError
from app.core.logging import get_logger, log_event
from app.graphs.base import MAX_ATTEMPTS, BaseState, capture_errors
from app.graphs.checkpointer import get_checkpointer
from app.graphs.recruiter.prompts import ERROR_REPLY, SYSTEM_PROMPT
from app.graphs.recruiter.tools import (
    EXTERNAL_ACTIONS,
    TOOL_HANDLERS,
    TOOL_SCHEMAS,
    TOOL_SCHEMAS_BY_NAME,
)

logger = get_logger(__name__)


class RecruiterState(BaseState, total=False):
    # The conversation. add_messages appends new messages instead of
    # replacing the list.
    messages: Annotated[list[AnyMessage], add_messages]
    user_id: int
    saved_job_id: int | None


def get_agent_model() -> Runnable[LanguageModelInput, AIMessage]:
    """The chat model with the agent's tools attached."""
    return get_chat_model().bind_tools(TOOL_SCHEMAS)


def load_context(state: RecruiterState) -> dict:
    """Start each turn with a clean error state."""
    return {"error": None, "attempts": 0}


@capture_errors
def agent(state: RecruiterState) -> dict:
    """Ask the model what to do next: answer, or use a tool."""
    messages = [SystemMessage(SYSTEM_PROMPT), *state["messages"]]
    response = run_with_retries(
        "recruiter_agent", lambda: get_agent_model().invoke(messages)
    )
    return {"messages": [response]}


def route_after_agent(
    state: RecruiterState,
) -> Literal["respond", "call_tools", "human_approval", "handle_error"]:
    """Choose the next node from what the model returned."""
    if state.get("error"):
        return "handle_error"
    tool_calls = state["messages"][-1].tool_calls
    if not tool_calls:
        return "respond"
    if any(call["name"] in EXTERNAL_ACTIONS for call in tool_calls):
        return "human_approval"
    return "call_tools"


def human_approval(
    state: RecruiterState,
) -> Command[Literal["call_tools", "agent", "handle_error"]]:
    """Pause until the interviewer approves or rejects the action.

    The details are checked first. If the model left something out or got a
    value wrong, it is asked to correct them, so the interviewer is only ever
    shown complete, valid details.
    """
    request = state["messages"][-1]
    call = request.tool_calls[0]
    try:
        schema = TOOL_SCHEMAS_BY_NAME[call["name"]]
        arguments = schema.model_validate(call["args"]).model_dump()
    except ValidationError as exc:
        attempts = state.get("attempts", 0) + 1
        problem = ToolMessage(content=_describe_failure(exc), tool_call_id=call["id"])
        return Command(
            goto="handle_error" if attempts >= MAX_ATTEMPTS else "agent",
            update={"messages": [problem], "attempts": attempts},
        )

    decision = interrupt({"action": call["name"], "arguments": arguments})

    if not decision.get("approved"):
        feedback = decision.get("feedback") or "No reason was given."
        rejection = ToolMessage(
            content=f"The interviewer did not approve this. Their feedback: {feedback}",
            tool_call_id=call["id"],
        )
        return Command(goto="agent", update={"messages": [rejection]})

    # Save the checked details, or the interviewer's edited version of them.
    # Replacing the message under the same id keeps the conversation consistent.
    approved_call = {**call, "args": decision.get("arguments") or arguments}
    approved = AIMessage(
        content=request.content, tool_calls=[approved_call], id=request.id
    )
    return Command(goto="call_tools", update={"messages": [approved]})


def call_tools(state: RecruiterState) -> Command[Literal["agent", "handle_error"]]:
    """Run the tools the model asked for and give it the results."""
    attempts = state.get("attempts", 0)
    update: dict = {"messages": []}

    for call in state["messages"][-1].tool_calls:
        try:
            content, changes = TOOL_HANDLERS[call["name"]](call["args"], state)
            update.update(changes)
        except Exception as exc:
            attempts += 1
            content = _describe_failure(exc)
            log_event(
                logger,
                "tool_call_failed",
                level=logging.WARNING,
                tool=call["name"],
                attempt=attempts,
                error_type=type(exc).__name__,
            )
        update["messages"].append(ToolMessage(content=content, tool_call_id=call["id"]))

    update["attempts"] = attempts
    goto = "handle_error" if attempts >= MAX_ATTEMPTS else "agent"
    return Command(goto=goto, update=update)


def _describe_failure(exc: Exception) -> str:
    """Tell the model what went wrong, so it can correct itself and retry."""
    if isinstance(exc, ValidationError):
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        return f"The details were not valid. Fix these and try again: {problems}"
    if isinstance(exc, AppError):
        return f"The action failed: {exc.message}"
    return "The action failed because of an unexpected problem."


def handle_error(state: RecruiterState) -> dict:
    """Give the interviewer a clear message when the turn cannot be completed."""
    return {"messages": [AIMessage(ERROR_REPLY)], "error": None}


def respond(state: RecruiterState) -> dict:
    """The last node of every turn. The reply is the final message."""
    return {}


def build_recruiter_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    graph = StateGraph(RecruiterState)
    graph.add_node("load_context", load_context)
    graph.add_node("agent", agent)
    graph.add_node("human_approval", human_approval)
    graph.add_node("call_tools", call_tools)
    graph.add_node("handle_error", handle_error)
    graph.add_node("respond", respond)

    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "agent")
    graph.add_conditional_edges("agent", route_after_agent)
    graph.add_edge("handle_error", "respond")
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=checkpointer)


@lru_cache
def get_recruiter_graph() -> CompiledStateGraph:
    """The Recruiter Agent with PostgreSQL checkpoints, built once."""
    return build_recruiter_graph(get_checkpointer())
