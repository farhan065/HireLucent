"""LangGraph 4: Final Assessment.

Turns one interview's Q&A analysis into a consolidated report, which the
interviewer reviews before it counts:

    start -> load_results -> (analysis found)   -> compute_scores
                          -> (analysis missing) -> handle_error -> end
    compute_scores -> synthesize_report
    synthesize_report -> (answer received)       -> check_traceability
                      -> (AI not available, first draft) -> handle_error -> end
                      -> (AI not available, rewriting)   -> human_review
    check_traceability -> (every claim traced, or no attempts left) -> save_draft
                       -> (untraced claims, attempts left)          -> synthesize_report
    save_draft -> human_review (pauses for the interviewer)
    human_review -> (approve)         -> save_assessment -> update_candidate_status -> end
                 -> (request changes) -> synthesize_report, with the note
                 -> (edit)            -> apply_edits -> save_draft

compute_scores (rule-based) works out the CV, interview and overall scores,
the suitability label, the evidence gaps and the areas to verify.
synthesize_report asks the AI for the summary, strengths and weaknesses, and
check_traceability checks that each strength and weakness points to a real
quote or CV result (see report.py). Claims still untraced after the last
attempt are left out.

The interviewer's edit can change the summary and remove strengths or
weaknesses, never add one, because a typed claim would have no evidence.
"""

import logging
from functools import lru_cache
from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from app.core.errors import ServiceUnavailableError
from app.core.logging import get_logger, log_event
from app.graphs.base import BaseState, can_retry
from app.graphs.checkpointer import get_checkpointer
from app.graphs.final_assessment import findings, report, scoring, store

logger = get_logger(__name__)

NOT_ANALYSED = "This interview's answers have not been evaluated."
AI_UNAVAILABLE = (
    "The AI service was not available to write the report. "
    "Evaluate the interview again to retry."
)
NO_SUMMARY = "The AI could not write a usable report. Evaluate the interview again to retry."

APPROVE = "approve"
REQUEST_CHANGES = "request_changes"
EDIT = "edit"


class FinalState(BaseState, total=False):
    session_id: int
    candidate_id: int
    job_title: str
    # From the Q&A analysis: the evaluated pairs and the requirement coverage.
    pairs: list[dict]
    coverage: list[dict]
    # The candidate's turns, to check the quotes the AI gives.
    turns: list[dict]
    cv_score: float | None
    interview_score: float | None
    overall_score: float | None
    # The report: the summary and four lists of claims with their sources.
    summary: str
    strengths: list[dict]
    weaknesses: list[dict]
    gaps: list[dict]
    areas_to_verify: list[dict]
    # The AI's latest answer and what the traceability check found in it.
    proposal: dict
    problems: list[str]
    # The interviewer's review.
    decision: str
    note: str | None
    edits: dict
    reviewer_id: int
    # True when the AI could not rewrite the report on request; the draft
    # is unchanged and waits for review again.
    revision_failed: bool
    # Set when no report can be made. The message is safe to show.
    failure: str


def _turns(state: FinalState) -> dict[int, dict]:
    return {turn["id"]: turn for turn in state["turns"]}


def _draft(state: FinalState) -> dict | None:
    if not state.get("summary"):
        return None
    return {
        "summary": state["summary"],
        "strengths": state.get("strengths", []),
        "weaknesses": state.get("weaknesses", []),
    }


def load_results(state: FinalState) -> dict:
    """Read the Q&A analysis and the CV screening score."""
    results = store.load_results(state["session_id"])
    if results is None:
        return {"failure": NOT_ANALYSED}
    return {**results, "attempts": 0}


def route_after_load(state: FinalState) -> Literal["compute_scores", "handle_error"]:
    return "handle_error" if state.get("failure") else "compute_scores"


def compute_scores(state: FinalState) -> dict:
    """The component scores, the evidence gaps and the areas to verify. No AI
    call."""
    interview = scoring.interview_score(state["pairs"])
    return {
        "interview_score": interview,
        "overall_score": scoring.overall_score(state.get("cv_score"), interview),
        "gaps": findings.evidence_gaps(state["coverage"]),
        "areas_to_verify": findings.areas_to_verify(state["pairs"], state["coverage"]),
    }


def synthesize_report(state: FinalState) -> dict:
    """Ask the AI for the summary, strengths and weaknesses. A request for
    changes sends the draft and the interviewer's note with it."""
    attempts = state.get("attempts", 0) + 1
    scores = {
        "cv": state.get("cv_score"),
        "interview": state.get("interview_score"),
        "overall": state.get("overall_score"),
    }
    try:
        answer = report.ask_ai(
            state["job_title"],
            scores,
            state["pairs"],
            state["coverage"],
            _turns(state),
            draft=_draft(state),
            note=state.get("note"),
            problems=state.get("problems"),
        )
    except ServiceUnavailableError:
        if _draft(state):
            return {"revision_failed": True, "attempts": attempts}
        return {"failure": AI_UNAVAILABLE, "attempts": attempts}
    return {"proposal": answer.model_dump(), "attempts": attempts}


def route_after_synthesize(
    state: FinalState,
) -> Literal["check_traceability", "human_review", "handle_error"]:
    if state.get("failure"):
        return "handle_error"
    if state.get("revision_failed"):
        return "human_review"
    return "check_traceability"


def check_traceability(state: FinalState) -> dict:
    """Check that every strength and weakness points to a real quote or CV
    result. Untraced claims are asked for again while attempts are left,
    then left out."""
    answer = report.ReportAnswer.model_validate(state["proposal"])
    turns = _turns(state)
    found = report.problems(answer, state["pairs"], state["coverage"], turns)
    if found and can_retry(state):
        log_event(
            logger,
            "assessment_report_untraced",
            level=logging.WARNING,
            session_id=state["session_id"],
            attempt=state["attempts"],
            problems=sorted(set(found)),
        )
        return {"problems": found}
    traced = report.traced_report(answer, state["pairs"], state["coverage"], turns)
    if not traced["summary"]:
        return {"failure": NO_SUMMARY, "problems": found}
    if traced["dropped"]:
        log_event(
            logger,
            "assessment_claims_dropped",
            level=logging.WARNING,
            session_id=state["session_id"],
            dropped=traced["dropped"],
        )
    return {
        "summary": traced["summary"],
        "strengths": traced["strengths"],
        "weaknesses": traced["weaknesses"],
        "problems": [],
    }


def route_after_check(
    state: FinalState,
) -> Literal["save_draft", "synthesize_report", "handle_error"]:
    if state.get("failure"):
        return "handle_error"
    return "synthesize_report" if state.get("problems") else "save_draft"


def save_draft(state: FinalState) -> dict:
    """Keep the report as a draft, so it shows as waiting for review."""
    store.save_draft(state["session_id"], state)
    log_event(
        logger,
        "assessment_draft_saved",
        session_id=state["session_id"],
        strengths=len(state.get("strengths", [])),
        weaknesses=len(state.get("weaknesses", [])),
        gaps=len(state.get("gaps", [])),
        areas_to_verify=len(state.get("areas_to_verify", [])),
    )
    return {}


def human_review(state: FinalState) -> dict:
    """Pause until the interviewer approves the draft, asks for changes with
    a note, or edits it."""
    review = interrupt({"session_id": state["session_id"]})
    return {
        "decision": review["action"],
        "note": review.get("note"),
        "edits": {
            "summary": review.get("summary"),
            "remove": review.get("remove") or [],
        },
        "reviewer_id": review["user_id"],
        "revision_failed": False,
        # A rewrite gets a fresh set of attempts.
        "attempts": 0,
        "problems": [],
    }


def route_after_review(
    state: FinalState,
) -> Literal["save_assessment", "synthesize_report", "apply_edits"]:
    if state["decision"] == APPROVE:
        return "save_assessment"
    if state["decision"] == REQUEST_CHANGES:
        return "synthesize_report"
    return "apply_edits"


def apply_edits(state: FinalState) -> dict:
    """The interviewer's own changes: a new summary, and strengths or
    weaknesses removed. Nothing can be added."""
    edits = state.get("edits", {})
    removed = set(edits.get("remove", []))
    update: dict = {
        "strengths": [claim for claim in state["strengths"] if claim["id"] not in removed],
        "weaknesses": [claim for claim in state["weaknesses"] if claim["id"] not in removed],
    }
    if edits.get("summary"):
        update["summary"] = edits["summary"].strip()[: report.MAX_SUMMARY_CHARS]
    return update


def save_assessment(state: FinalState) -> dict:
    """Keep the approved report, with who approved it and when."""
    store.approve(state["session_id"], state["reviewer_id"])
    log_event(
        logger,
        "assessment_approved",
        session_id=state["session_id"],
        reviewer_id=state["reviewer_id"],
    )
    return {}


def update_candidate_status(state: FinalState) -> dict:
    store.mark_assessed(state["candidate_id"])
    return {}


def handle_error(state: FinalState) -> dict:
    """Record why no report was made. The Q&A analysis stays saved."""
    log_event(
        logger,
        "final_assessment_failed",
        level=logging.WARNING,
        session_id=state["session_id"],
        attempts=state.get("attempts", 0),
    )
    return {"failure": state.get("failure") or NO_SUMMARY}


def build_final_assessment_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    graph = StateGraph(FinalState)
    graph.add_node("load_results", load_results)
    graph.add_node("compute_scores", compute_scores)
    graph.add_node("synthesize_report", synthesize_report)
    graph.add_node("check_traceability", check_traceability)
    graph.add_node("save_draft", save_draft)
    graph.add_node("human_review", human_review)
    graph.add_node("apply_edits", apply_edits)
    graph.add_node("save_assessment", save_assessment)
    graph.add_node("update_candidate_status", update_candidate_status)
    graph.add_node("handle_error", handle_error)

    graph.add_edge(START, "load_results")
    graph.add_conditional_edges("load_results", route_after_load)
    graph.add_edge("compute_scores", "synthesize_report")
    graph.add_conditional_edges("synthesize_report", route_after_synthesize)
    graph.add_conditional_edges("check_traceability", route_after_check)
    graph.add_edge("save_draft", "human_review")
    graph.add_conditional_edges("human_review", route_after_review)
    graph.add_edge("apply_edits", "save_draft")
    graph.add_edge("save_assessment", "update_candidate_status")
    graph.add_edge("update_candidate_status", END)
    graph.add_edge("handle_error", END)
    return graph.compile(checkpointer=checkpointer)


@lru_cache
def get_final_assessment_graph() -> CompiledStateGraph:
    """The Final Assessment graph with PostgreSQL checkpoints, built once."""
    return build_final_assessment_graph(get_checkpointer())


def thread_id(session_id: int) -> str:
    """One thread per interview, so a review can find the paused report.
    Evaluating the interview again starts the thread afresh."""
    return f"final-assessment-{session_id}"


def is_waiting_for_review(graph: CompiledStateGraph, config: dict) -> bool:
    return graph.get_state(config).next == ("human_review",)
