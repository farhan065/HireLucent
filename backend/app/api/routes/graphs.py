"""Endpoints for the demo graph (start, check, resume)."""

from uuid import uuid4

from fastapi import APIRouter, Depends
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from app.api.deps import require_interviewer
from app.core.errors import ConflictError, NotFoundError
from app.graphs.base import thread_config
from app.graphs.demo import get_demo_graph
from app.schemas.graph import DemoResumeRequest, DemoRunResponse, DemoStartRequest

router = APIRouter(
    prefix="/graphs/demo",
    tags=["Graph demo"],
    dependencies=[Depends(require_interviewer)],
)


def _describe(graph: CompiledStateGraph, thread_id: str) -> DemoRunResponse:
    """Read the saved state of one run and report where it stands."""
    snapshot = graph.get_state(thread_config(thread_id))
    if not snapshot.values:
        raise NotFoundError("This run does not exist.")
    waiting = bool(snapshot.next)
    return DemoRunResponse(
        thread_id=thread_id,
        status="waiting_for_approval" if waiting else "finished",
        draft=snapshot.values.get("draft"),
        result=snapshot.values.get("result"),
    )


@router.post("", response_model=DemoRunResponse, summary="Start a demo run")
def start_run(
    payload: DemoStartRequest, graph: CompiledStateGraph = Depends(get_demo_graph)
) -> DemoRunResponse:
    """Run the graph until it pauses for approval or ends."""
    thread_id = uuid4().hex
    graph.invoke({"text": payload.text}, thread_config(thread_id))
    return _describe(graph, thread_id)


@router.get("/{thread_id}", response_model=DemoRunResponse, summary="Check a demo run")
def read_run(
    thread_id: str, graph: CompiledStateGraph = Depends(get_demo_graph)
) -> DemoRunResponse:
    return _describe(graph, thread_id)


@router.post(
    "/{thread_id}/resume", response_model=DemoRunResponse, summary="Approve or reject"
)
def resume_run(
    thread_id: str,
    payload: DemoResumeRequest,
    graph: CompiledStateGraph = Depends(get_demo_graph),
) -> DemoRunResponse:
    """Continue a paused run with the human's decision."""
    if _describe(graph, thread_id).status == "finished":
        raise ConflictError("This run has already finished.")
    graph.invoke(Command(resume=payload.approved), thread_config(thread_id))
    return _describe(graph, thread_id)