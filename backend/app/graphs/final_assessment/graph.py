"""LangGraph 4: Final Assessment.

Turns one interview's Q&A analysis into a consolidated report, which the
interviewer reviews before it counts:

    start -> load_results -> (analysis found)   -> compute_scores
                          -> (claims only)      -> extract_claims
                          -> (analysis missing) -> handle_error -> end
    compute_scores -> extract_claims
    extract_claims -> (claims to judge) -> judge_claims
                   -> (none)            -> save_claims
    judge_claims -> (answer received)  -> check_claims
                 -> (AI not available) -> save_claims (claims not checked)
    check_claims -> (untraced claims, attempts left) -> judge_claims
                 -> (all checked, or no attempts left) -> save_claims
    save_claims -> (claims only) -> end
                -> (full run)    -> synthesize_report
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

The CV claim check (F8) compares every claim in the CV with what the
candidate said: extract_claims takes the claims from the CV (code),
judge_claims asks the AI for each one's result and check_claims proves each
quote is in the transcript (see claims.py). Its results are saved apart from
the report and never change a score or the report. If the AI is not
available the claims are saved as not checked and the report is still
written. Check CV claims (an interview evaluated before F8) and Check again
run only these nodes, on their own thread, so a report, its approval and the
decision stay as they are.
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
from app.graphs.base import MAX_ATTEMPTS, BaseState, can_retry
from app.graphs.checkpointer import get_checkpointer
from app.graphs.final_assessment import claims as cv_claims
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
    # True for Check CV claims / Check again: only the claim nodes run.
    claims_only: bool
    candidate_id: int
    job_title: str
    # From the Q&A analysis: the evaluated pairs and the requirement coverage.
    pairs: list[dict]
    coverage: list[dict]
    # The candidate's turns, to check the quotes the AI gives.
    turns: list[dict]
    # The CV facts (no contact details), for the claim check.
    cv: dict | None
    # The claim check (F8): the claims, the results that passed the check
    # by claim id, the claims still to judge with their problems, the AI's
    # latest answers, its own attempt count and whether the AI was down.
    claims: list[dict]
    claim_results: dict[str, dict]
    claims_pending: list[str]
    claim_problems: dict[str, list[str]]
    claim_proposals: list[dict]
    claim_attempts: int
    claims_failed: bool
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


def route_after_load(
    state: FinalState,
) -> Literal["compute_scores", "extract_claims", "handle_error"]:
    if state.get("failure"):
        return "handle_error"
    return "extract_claims" if state.get("claims_only") else "compute_scores"


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


def extract_claims(state: FinalState) -> dict:
    """The claims in the CV, taken by code. When the candidate answered
    nothing, every claim is not discussed, with no AI call."""
    claims = cv_claims.extract_claims(state.get("cv"))
    results: dict[str, dict] = {}
    pending = [claim["id"] for claim in claims]
    if claims and not cv_claims.answered_pairs(state["pairs"]):
        results = {claim["id"]: cv_claims.not_discussed(claim) for claim in claims}
        pending = []
    return {
        "claims": claims,
        "claim_results": results,
        "claims_pending": pending,
        "claim_problems": {},
        "claim_attempts": 0,
        "claims_failed": False,
    }


def route_after_extract(state: FinalState) -> Literal["judge_claims", "save_claims"]:
    return "judge_claims" if state["claims_pending"] else "save_claims"


def judge_claims(state: FinalState) -> dict:
    """Ask the AI for the result of each claim still to judge, a batch at a
    time, with the problems of its previous answer for those claims."""
    attempts = state.get("claim_attempts", 0) + 1
    by_id = {claim["id"]: claim for claim in state["claims"]}
    pending = [by_id[claim_id] for claim_id in state["claims_pending"]]
    problems = state.get("claim_problems", {})
    proposals = []
    try:
        for start in range(0, len(pending), cv_claims.BATCH_SIZE):
            batch = pending[start : start + cv_claims.BATCH_SIZE]
            labels = [label for claim in batch for label in problems.get(claim["id"], [])]
            answer = cv_claims.ask_ai(
                state["job_title"], batch, state["pairs"], _turns(state), problems=labels
            )
            proposals.append(answer.model_dump())
    except ServiceUnavailableError:
        return {"claims_failed": True, "claim_attempts": attempts}
    return {"claim_proposals": proposals, "claim_attempts": attempts}


def route_after_judge(state: FinalState) -> Literal["check_claims", "save_claims"]:
    return "save_claims" if state.get("claims_failed") else "check_claims"


def check_claims(state: FinalState) -> dict:
    """Check each result: the quote must be in the candidate's answer to the
    question named, and the reason must be neutral. Failing claims are asked
    for again while attempts are left, then kept as not checked."""
    by_id = {claim["id"]: claim for claim in state["claims"]}
    pending = [by_id[claim_id] for claim_id in state["claims_pending"]]
    answer = cv_claims.ClaimsAnswer(
        results=[
            item
            for proposal in state.get("claim_proposals", [])
            for item in cv_claims.ClaimsAnswer.model_validate(proposal).results
        ]
    )
    accepted, problems = cv_claims.check_answer(answer, pending, state["pairs"], _turns(state))
    results = {**state.get("claim_results", {}), **accepted}
    labels = sorted({label for found in problems.values() for label in found})
    if problems and state["claim_attempts"] < MAX_ATTEMPTS:
        log_event(
            logger,
            "cv_claims_invalid",
            level=logging.WARNING,
            session_id=state["session_id"],
            attempt=state["claim_attempts"],
            claims=len(problems),
            problems=labels,
        )
        return {
            "claim_results": results,
            "claims_pending": list(problems),
            "claim_problems": problems,
        }
    if problems:
        log_event(
            logger,
            "cv_claims_not_traced",
            level=logging.WARNING,
            session_id=state["session_id"],
            claims=len(problems),
            problems=labels,
        )
    for claim_id in problems:
        results[claim_id] = cv_claims.not_checked(by_id[claim_id])
    return {"claim_results": results, "claims_pending": [], "claim_problems": {}}


def route_after_claims_check(state: FinalState) -> Literal["judge_claims", "save_claims"]:
    return "judge_claims" if state["claims_pending"] else "save_claims"


def save_claims(state: FinalState) -> dict:
    """Keep the claim check with the assessment, apart from the report."""
    checks = cv_claims.claim_checks(
        state.get("claims", []),
        state.get("claim_results", {}),
        failed=state.get("claims_failed", False),
    )
    store.save_claim_checks(state["session_id"], checks)
    log_event(
        logger,
        "cv_claims_checked",
        session_id=state["session_id"],
        status=checks["status"],
        attempts=state.get("claim_attempts", 0),
        results=cv_claims.counts(checks),
    )
    return {}


def route_after_save_claims(state: FinalState) -> Literal["synthesize_report", "__end__"]:
    return END if state.get("claims_only") else "synthesize_report"


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
    graph.add_node("extract_claims", extract_claims)
    graph.add_node("judge_claims", judge_claims)
    graph.add_node("check_claims", check_claims)
    graph.add_node("save_claims", save_claims)
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
    graph.add_edge("compute_scores", "extract_claims")
    graph.add_conditional_edges("extract_claims", route_after_extract)
    graph.add_conditional_edges("judge_claims", route_after_judge)
    graph.add_conditional_edges("check_claims", route_after_claims_check)
    graph.add_conditional_edges("save_claims", route_after_save_claims)
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


def claims_thread_id(session_id: int) -> str:
    """The thread of a run of the claim check alone (Check CV claims, Check
    again), kept apart from the report's thread, which may be waiting for
    review."""
    return f"cv-claims-{session_id}"


def is_waiting_for_review(graph: CompiledStateGraph, config: dict) -> bool:
    return graph.get_state(config).next == ("human_review",)
