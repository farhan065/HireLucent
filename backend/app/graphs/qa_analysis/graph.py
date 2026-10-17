"""LangGraph 3: Q&A Analysis.

Turns one interview's transcript into question-answer pairs:

    start -> load_transcript -> (transcript ready)   -> segment_qa
                             -> (transcript missing) -> handle_error -> end
    segment_qa -> (pairs found)                        -> save_analysis -> end
               -> (no valid pairs, attempts left)      -> segment_qa
               -> (AI not available, or still no pairs) -> handle_error -> end

segment_qa's answer is checked against the real transcript (see
segmentation.build_pairs). An answer with no valid pair is asked for again,
up to MAX_ATTEMPTS times. Evaluating each answer, checking it against the
Knowledge Base and mapping the job's requirements follow in later steps.
"""

import logging
from functools import lru_cache
from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.core.errors import ServiceUnavailableError
from app.core.logging import get_logger, log_event
from app.graphs.base import BaseState, can_retry
from app.graphs.checkpointer import get_checkpointer
from app.graphs.qa_analysis import segmentation, store
from app.models.enums import SessionStatus

logger = get_logger(__name__)

NOT_FOUND = "This interview no longer exists."
NOT_COMPLETED = "Only a completed interview can be evaluated."
NO_TRANSCRIPT = "This interview has no transcript with both people speaking."
AI_UNAVAILABLE = "The AI service was not available. Evaluate the interview again to retry."
NO_PAIRS = "No questions and answers could be found in the transcript."


class QAState(BaseState, total=False):
    session_id: int
    candidate_id: int
    job_title: str
    # The transcript turns: id, speaker, start_ms, end_ms and text.
    turns: list[dict]
    # The question-answer pairs (see segmentation.build_pairs).
    pairs: list[dict]
    # Set when the analysis cannot be done. The message is safe to show.
    failure: str


def load_transcript(state: QAState) -> dict:
    """Read the interview and its transcript from the database."""
    interview = store.load_interview(state["session_id"])
    if interview is None:
        return {"failure": NOT_FOUND}
    if interview["status"] != SessionStatus.COMPLETED:
        return {"failure": NOT_COMPLETED}
    if not segmentation.has_conversation(interview["turns"]):
        return {"failure": NO_TRANSCRIPT}
    return {
        "candidate_id": interview["candidate_id"],
        "job_title": interview["job_title"],
        "turns": interview["turns"],
        "attempts": 0,
    }


def route_after_load(state: QAState) -> Literal["segment_qa", "handle_error"]:
    return "handle_error" if state.get("failure") else "segment_qa"


def segment_qa(state: QAState) -> dict:
    """Ask the AI to split the transcript into pairs, then check them."""
    attempts = state.get("attempts", 0) + 1
    try:
        answer = segmentation.ask_ai(state["job_title"], state["turns"])
    except ServiceUnavailableError:
        return {"failure": AI_UNAVAILABLE, "attempts": attempts}
    pairs = segmentation.build_pairs(answer, state["turns"])
    if not pairs:
        log_event(
            logger,
            "qa_segmentation_empty",
            level=logging.WARNING,
            session_id=state["session_id"],
            attempt=attempts,
        )
    return {"pairs": pairs, "attempts": attempts}


def route_after_segment(
    state: QAState,
) -> Literal["save_analysis", "segment_qa", "handle_error"]:
    if state.get("failure"):
        return "handle_error"
    if state["pairs"]:
        return "save_analysis"
    return "segment_qa" if can_retry(state) else "handle_error"


def save_analysis(state: QAState) -> dict:
    """Keep the pairs on the interview's assessment."""
    store.save_analysis(state["session_id"], state["candidate_id"], state["pairs"])
    log_event(
        logger,
        "qa_analysis_saved",
        session_id=state["session_id"],
        **segmentation.counts(state["pairs"]),
    )
    return {}


def handle_error(state: QAState) -> dict:
    """Record why the analysis stopped. Nothing is saved."""
    failure = state.get("failure") or NO_PAIRS
    log_event(
        logger,
        "qa_analysis_failed",
        level=logging.WARNING,
        session_id=state["session_id"],
        attempts=state.get("attempts", 0),
    )
    return {"failure": failure}


def build_qa_analysis_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    graph = StateGraph(QAState)
    graph.add_node("load_transcript", load_transcript)
    graph.add_node("segment_qa", segment_qa)
    graph.add_node("save_analysis", save_analysis)
    graph.add_node("handle_error", handle_error)

    graph.add_edge(START, "load_transcript")
    graph.add_conditional_edges("load_transcript", route_after_load)
    graph.add_conditional_edges("segment_qa", route_after_segment)
    graph.add_edge("save_analysis", END)
    graph.add_edge("handle_error", END)
    return graph.compile(checkpointer=checkpointer)


@lru_cache
def get_qa_analysis_graph() -> CompiledStateGraph:
    """The Q&A Analysis graph with PostgreSQL checkpoints, built once."""
    return build_qa_analysis_graph(get_checkpointer())
