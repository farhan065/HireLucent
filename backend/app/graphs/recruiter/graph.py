"""LangGraph 1: the Recruiter Agent.

    start -> load_context -> agent
    agent -> respond              (a plain answer)
    agent -> call_tools           (a read-only tool)
    agent -> human_approval       (an action that needs approval)
    human_approval -> call_tools      (approved)
    human_approval -> human_approval  (edited by the interviewer)
    human_approval -> agent           (rejected, with feedback)
    call_tools -> agent           (tool result)
    call_tools -> handle_error    (too many failed attempts)
    handle_error -> respond -> end

In an interview room the same graph runs in a read-only interview mode:
load_context adds the interview's details, the model is given only the
question bank search, and every other tool is refused in call_tools, so
nothing can be changed and human_approval is never reached. The question
bank search is always kept to the job's role by call_tools, never by the
model.
"""

import json
import logging
from datetime import datetime, timezone
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
from app.ai.models import get_chat_model, get_room_chat_model
from app.ai.usage import usage_context
from app.core.config import get_settings
from app.core.errors import AppError, ServiceUnavailableError
from app.core.logging import get_logger, log_event
from app.graphs.base import MAX_ATTEMPTS, BaseState, capture_errors
from app.graphs.checkpointer import get_checkpointer
from app.graphs.recruiter.prompts import (
    ERROR_REPLY,
    FEEDBACK_LABEL,
    INTERVIEW_PROMPT,
    NO_REASON,
    REJECTED_PREFIX,
    ROOM_BUSY_REPLY,
    ROOM_ERROR_REPLY,
    SYSTEM_PROMPT,
)
from app.mcp_clients import client as mcp_client
from app.services import interview_context
from app.services.interview_times import now_description
from app.graphs.recruiter.tools import (
    EXTERNAL_ACTIONS,
    INTERVIEW_TOOLS,
    PREPARERS,
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
    # Set in an interview room: the interview, and what the AI is told
    # about it, loaded again at the start of every turn.
    interview_id: int | None
    interview_details: str | None
    interview_role: str | None


SEARCH_UNAVAILABLE = "The search is not available right now. Continue without it."
NOT_IN_INTERVIEW = "This tool is not available during an interview. Only answer."


def _without_role(tool: dict) -> dict:
    """The tool as the model sees it, without the role parameter, which the
    application fills in itself."""
    function = tool["function"]
    parameters = dict(function.get("parameters") or {})
    parameters["properties"] = {
        name: value
        for name, value in (parameters.get("properties") or {}).items()
        if name != "role"
    }
    if "required" in parameters:
        parameters["required"] = [name for name in parameters["required"] if name != "role"]
    return {**tool, "function": {**function, "parameters": parameters}}


def _mcp_tools(interview: bool) -> list[dict]:
    """The MCP search tools for one mode: the question bank in an interview,
    the job description search otherwise."""
    return [
        _without_role(tool) if interview else tool
        for tool in mcp_client.agent_tool_definitions()
        if (tool["function"]["name"] in INTERVIEW_TOOLS) == interview
    ]


def get_agent_model() -> Runnable[LanguageModelInput, AIMessage]:
    """The chat model with the agent's tools attached: our own tools and
    the search tools offered by the MCP server."""
    tools = [*TOOL_SCHEMAS, *_mcp_tools(interview=False)]
    return get_chat_model().bind_tools(tools)


def get_interview_model() -> Runnable[LanguageModelInput, AIMessage]:
    """The chat model for an interview room, with the question bank search
    as its only tool. It waits less than the AI Agent page does."""
    tools = _mcp_tools(interview=True)
    model = get_room_chat_model()
    return model.bind_tools(tools) if tools else model


def _in_interview(state: RecruiterState) -> bool:
    return bool(state.get("interview_id"))


def load_context(state: RecruiterState) -> dict:
    """Start each turn with a clean error state. In an interview room, load
    the interview's job and candidate details too."""
    update: dict = {"error": None, "attempts": 0}
    if _in_interview(state):
        details, role = interview_context.for_session(state["interview_id"])
        update.update({"interview_details": details, "interview_role": role})
    return update


@capture_errors
def agent(state: RecruiterState) -> dict:
    """Ask the model what to do next: answer, or use a tool."""
    max_attempts = None
    if _in_interview(state):
        prompt = f"{INTERVIEW_PROMPT}{state.get('interview_details') or ''}"
        model = get_interview_model()
        # Fewer tries, so a slow AI service gives up within about a minute.
        max_attempts = get_settings().room_ai_max_attempts
    else:
        # Today's date, so a day such as "Tuesday" means the right one.
        prompt = f"{SYSTEM_PROMPT}\n{now_description(datetime.now(timezone.utc))}"
        model = get_agent_model()
    messages = [SystemMessage(prompt), *state["messages"]]
    with usage_context(job_id=state.get("saved_job_id")):
        response = run_with_retries(
            "recruiter_agent", lambda: model.invoke(messages), max_attempts=max_attempts
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
    # In an interview nothing waits for approval: call_tools refuses
    # anything but the question bank search.
    if _in_interview(state):
        return "call_tools"
    if any(call["name"] in EXTERNAL_ACTIONS for call in tool_calls):
        return "human_approval"
    return "call_tools"


def human_approval(
    state: RecruiterState,
) -> Command[Literal["call_tools", "agent", "handle_error", "human_approval"]]:
    """Pause until the interviewer approves, edits or rejects the action.

    The details are checked first. If the model left something out or got a
    value wrong, it is asked to correct them, so the interviewer is only ever
    shown complete, valid details.
    """
    request = state["messages"][-1]
    # The action to approve. If the model asked for other tools in the same
    # reply, they are dropped: one action is approved at a time.
    call = next(c for c in request.tool_calls if c["name"] in EXTERNAL_ACTIONS)
    name = call["name"]
    try:
        arguments = TOOL_SCHEMAS_BY_NAME[name].model_validate(call["args"]).model_dump()
        if name in PREPARERS:
            arguments = PREPARERS[name](arguments, state)
    except (ValidationError, AppError) as exc:
        attempts = state.get("attempts", 0) + 1
        problem = ToolMessage(content=_describe_failure(exc), tool_call_id=call["id"])
        return Command(
            goto="handle_error" if attempts >= MAX_ATTEMPTS else "agent",
            update={"messages": [problem], "attempts": attempts},
        )

    decision = interrupt({"action": name, "arguments": arguments})
    edited = decision.get("arguments")

    if decision.get("approved"):
        # Prepared details are used as shown. Otherwise the interviewer's
        # edited version, if any, replaces the checked details.
        final = arguments if name in PREPARERS else (edited or arguments)
        return Command(
            goto="call_tools",
            update={"messages": [_with_arguments(request, call, final)]},
        )

    if edited:
        # The interviewer changed the details directly. Check the new ones
        # and ask again, without involving the model.
        return Command(
            goto="human_approval",
            update={"messages": [_with_arguments(request, call, edited)]},
        )

    feedback = decision.get("feedback") or NO_REASON
    rejection = ToolMessage(
        content=f"{REJECTED_PREFIX}{FEEDBACK_LABEL}{feedback}",
        tool_call_id=call["id"],
    )
    return Command(goto="agent", update={"messages": [rejection]})


def _with_arguments(request: AIMessage, call: dict, arguments: dict) -> AIMessage:
    """The same tool request with different arguments. Keeping the message
    id replaces the original, so the conversation stays consistent."""
    call = {**call, "args": arguments}
    return AIMessage(content=request.content, tool_calls=[call], id=request.id)


def call_tools(state: RecruiterState) -> Command[Literal["agent", "handle_error"]]:
    """Run the tools the model asked for and give it the results."""
    attempts = state.get("attempts", 0)
    update: dict = {"messages": []}

    for call in state["messages"][-1].tool_calls:
        if _in_interview(state) and call["name"] not in INTERVIEW_TOOLS:
            attempts += 1
            log_event(logger, "interview_tool_refused", level=logging.WARNING, tool=call["name"])
            update["messages"].append(
                ToolMessage(content=NOT_IN_INTERVIEW, tool_call_id=call["id"])
            )
            continue
        try:
            if call["name"] in TOOL_HANDLERS:
                content, changes = TOOL_HANDLERS[call["name"]](call["args"], state)
                update.update(changes)
            else:
                # Any other tool belongs to the MCP server. In an interview
                # the question bank is kept to the job's role.
                arguments = dict(call["args"])
                if _in_interview(state):
                    arguments["role"] = state.get("interview_role") or ""
                content = json.dumps(mcp_client.call_agent_tool(call["name"], arguments))
        except Exception as exc:
            attempts += 1
            is_ours = call["name"] in TOOL_HANDLERS
            content = _describe_failure(exc) if is_ours else SEARCH_UNAVAILABLE
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
    """Give the interviewer a clear message when the turn cannot be completed.

    In an interview room the reply says whether the AI service was busy,
    and is marked as failed so the room can show it differently."""
    if not _in_interview(state):
        return {"messages": [AIMessage(ERROR_REPLY)], "error": None}
    is_busy = state.get("error") == ServiceUnavailableError.__name__
    reply = AIMessage(
        ROOM_BUSY_REPLY if is_busy else ROOM_ERROR_REPLY, additional_kwargs={"failed": True}
    )
    return {"messages": [reply], "error": None}


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
