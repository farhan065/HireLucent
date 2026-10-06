"""A small graph that proves the shared foundation works.

It drafts a line of text, pauses for human approval, then finishes. It uses
no AI model. The four real graphs follow the same pattern.
"""

from functools import lru_cache

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from app.graphs.base import BaseState, capture_errors, route_on_error
from app.graphs.checkpointer import get_checkpointer


class DemoState(BaseState, total=False):
    text: str
    draft: str
    approved: bool
    result: str


@capture_errors
def make_draft(state: DemoState) -> dict:
    """Prepare something for the human to review."""
    text = state["text"].strip()
    if not text:
        raise ValueError("Nothing to draft.")
    return {"draft": f"Draft: {text}"}


def human_approval(state: DemoState) -> dict:
    """Pause the graph until a person approves or rejects the draft."""
    approved = interrupt({"draft": state["draft"]})
    return {"approved": bool(approved)}


def finish(state: DemoState) -> dict:
    return {"result": "approved" if state["approved"] else "rejected"}


def handle_error(state: DemoState) -> dict:
    return {"result": "failed"}


def build_demo_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    """Connect the nodes and attach the checkpointer."""
    graph = StateGraph(DemoState)
    graph.add_node("make_draft", make_draft)
    graph.add_node("human_approval", human_approval)
    graph.add_node("finish", finish)
    graph.add_node("handle_error", handle_error)

    graph.add_edge(START, "make_draft")
    graph.add_conditional_edges(
        "make_draft",
        route_on_error("human_approval", "handle_error"),
        ["human_approval", "handle_error"],
    )
    graph.add_edge("human_approval", "finish")
    graph.add_edge("finish", END)
    graph.add_edge("handle_error", END)
    return graph.compile(checkpointer=checkpointer)


@lru_cache
def get_demo_graph() -> CompiledStateGraph:
    """The demo graph with PostgreSQL checkpoints, built once."""
    return build_demo_graph(get_checkpointer())