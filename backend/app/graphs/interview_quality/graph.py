"""LangGraph 6: Interview Quality (F10).

Looks at how one interview was run, not at the candidate: whether the
interviewer's questions gave useful answers, whether they explored the job's
requirements, and how the speaking time was shared. Then it writes a few
recommendations for the next interview.

    start -> load_interview -> (analysis found)   -> measure_interview
                            -> (analysis missing) -> handle_error -> end
    measure_interview -> score_quality -> find_issues
    find_issues -> (something to improve) -> write_recommendations
                -> (nothing found)        -> save_quality
    write_recommendations -> (answer received)  -> check_recommendations
                          -> (AI not available) -> save_quality (not written)
    check_recommendations -> (untraced, attempts left)            -> write_recommendations
                          -> (all traced, or no attempts left)     -> save_quality
    save_quality -> end

measure_interview, score_quality and find_issues are plain code
(measures.py): the speaking time per speaker from the transcript's times,
the three parts of the quality score and the label, and every finding with
the questions, requirements or times it rests on. write_recommendations is
the only AI step: it writes the recommendations from the findings, and
check_recommendations proves every id and number in them (see
recommendations.py). Recommendations still unproven after the last attempt
are left out. If the AI is not available, everything code measured is still
saved and the screens offer Check again.

It runs after the report is written (Evaluate, Evaluate again) and on its
own for an interview evaluated before F10 (Check interview quality). It
never changes a score of the candidate, the report, its approval or the
decision, and it is never sent to the candidate.
"""

import logging
from datetime import datetime, timezone
from functools import lru_cache
from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.core.errors import ServiceUnavailableError
from app.core.logging import get_logger, log_event
from app.graphs.base import BaseState, can_retry
from app.graphs.checkpointer import get_checkpointer
from app.graphs.interview_quality import measures, recommendations, store

logger = get_logger(__name__)

NOT_ANALYSED = "This interview's answers have not been evaluated."

CHECKED = "checked"
# The recommendations: written, none needed (nothing to improve), or not
# written because the AI was not available or none could be proven.
WRITTEN = "written"
NONE_NEEDED = "none_needed"
NOT_WRITTEN = "not_written"


class QualityState(BaseState, total=False):
    session_id: int
    job_title: str
    pairs: list[dict]
    coverage: list[dict]
    # Speaker, times and word count only; never the text.
    turns: list[dict]
    planned_ms: int | None
    actual_ms: int | None
    metrics: dict
    parts: dict
    score: float | None
    label: str | None
    findings: list[dict]
    # The most recommendations proven in one answer so far, and the
    # problems of the latest answer.
    recommendations: list[dict]
    problems: list[str]
    proposal: dict
    ai_failed: bool
    failure: str


def load_interview(state: QualityState) -> dict:
    """Read the Q&A analysis, the turns' times and the interview's length."""
    loaded = store.load_interview(state["session_id"])
    if loaded is None:
        return {"failure": NOT_ANALYSED}
    return {**loaded, "attempts": 0, "recommendations": [], "problems": [], "ai_failed": False}


def route_after_load(state: QualityState) -> Literal["measure_interview", "handle_error"]:
    return "handle_error" if state.get("failure") else "measure_interview"


def measure_interview(state: QualityState) -> dict:
    """Speaking time, the longest interviewer stretch, small talk, follow-ups
    and the length. No AI call."""
    return {
        "metrics": measures.measure(
            state["pairs"], state["turns"], state.get("planned_ms"), state.get("actual_ms")
        )
    }


def score_quality(state: QualityState) -> dict:
    """The three parts, the quality score and its label. No AI call."""
    turns = {turn["id"]: turn for turn in state["turns"]}
    parts = {
        "questions": measures.questions_part(state["pairs"], turns),
        "coverage": measures.coverage_part(state["coverage"]),
        "interaction": measures.interaction_part(state["metrics"]),
    }
    score = measures.score_parts(parts)
    return {"parts": parts, "score": score, "label": measures.label(score)}


def find_issues(state: QualityState) -> dict:
    """Everything to improve, each with what it rests on. No AI call."""
    return {
        "findings": measures.findings(
            state["pairs"], state["coverage"], state["metrics"], state["parts"]
        )
    }


def route_after_findings(state: QualityState) -> Literal["write_recommendations", "save_quality"]:
    return "write_recommendations" if state["findings"] else "save_quality"


def write_recommendations(state: QualityState) -> dict:
    """Ask the AI for the recommendations, with the problems of its previous
    answer."""
    attempts = state.get("attempts", 0) + 1
    try:
        answer = recommendations.ask_ai(
            state["job_title"], state["findings"], problems=state.get("problems")
        )
    except ServiceUnavailableError:
        return {"ai_failed": True, "attempts": attempts}
    return {"proposal": answer.model_dump(), "attempts": attempts}


def route_after_write(state: QualityState) -> Literal["check_recommendations", "save_quality"]:
    return "save_quality" if state.get("ai_failed") else "check_recommendations"


def check_recommendations(state: QualityState) -> dict:
    """Prove every finding id, question, requirement and number. The answer
    is asked for again while attempts are left; the most proven
    recommendations of any answer are kept."""
    answer = recommendations.RecommendationsAnswer.model_validate(state["proposal"])
    accepted, problems = recommendations.check_answer(answer, state["findings"])
    best = state.get("recommendations", [])
    if len(accepted) >= len(best):
        best = accepted
    if problems and can_retry(state):
        log_event(
            logger,
            "interview_quality_recommendations_invalid",
            level=logging.WARNING,
            session_id=state["session_id"],
            attempt=state["attempts"],
            problems=sorted(set(problems)),
        )
        return {"recommendations": best, "problems": problems}
    if problems:
        log_event(
            logger,
            "interview_quality_recommendations_dropped",
            level=logging.WARNING,
            session_id=state["session_id"],
            problems=sorted(set(problems)),
        )
    return {"recommendations": best, "problems": []}


def route_after_check(
    state: QualityState,
) -> Literal["write_recommendations", "save_quality"]:
    return "write_recommendations" if state.get("problems") else "save_quality"


def quality_result(state: QualityState) -> dict:
    """What is saved with the assessment."""
    findings = state.get("findings", [])
    items = state.get("recommendations", [])
    if not findings:
        status = NONE_NEEDED
    elif items:
        status = WRITTEN
    else:
        status = NOT_WRITTEN
    coverage = state["coverage"]
    return {
        "status": CHECKED,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "score": state.get("score"),
        "label": state.get("label"),
        "parts": state["parts"],
        "metrics": state["metrics"],
        "findings": findings,
        "recommendations": {
            "status": status,
            "reason": "ai_unavailable" if state.get("ai_failed") else None,
            "items": items,
        },
        "explored": measures.explored_requirements(coverage),
        "requirements": [
            {
                "id": entry["requirement_id"],
                "text": entry["text"],
                "priority": entry["priority"],
            }
            for entry in coverage
        ],
    }


def save_quality(state: QualityState) -> dict:
    result = quality_result(state)
    store.save_quality(state["session_id"], result)
    log_event(
        logger,
        "interview_quality_checked",
        session_id=state["session_id"],
        score=result["score"],
        label=result["label"],
        findings=len(result["findings"]),
        recommendations=len(result["recommendations"]["items"]),
        recommendations_status=result["recommendations"]["status"],
        attempts=state.get("attempts", 0),
    )
    return {}


def handle_error(state: QualityState) -> dict:
    log_event(
        logger,
        "interview_quality_failed",
        level=logging.WARNING,
        session_id=state["session_id"],
    )
    return {"failure": state.get("failure") or NOT_ANALYSED}


def build_interview_quality_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    graph = StateGraph(QualityState)
    graph.add_node("load_interview", load_interview)
    graph.add_node("measure_interview", measure_interview)
    graph.add_node("score_quality", score_quality)
    graph.add_node("find_issues", find_issues)
    graph.add_node("write_recommendations", write_recommendations)
    graph.add_node("check_recommendations", check_recommendations)
    graph.add_node("save_quality", save_quality)
    graph.add_node("handle_error", handle_error)

    graph.add_edge(START, "load_interview")
    graph.add_conditional_edges("load_interview", route_after_load)
    graph.add_edge("measure_interview", "score_quality")
    graph.add_edge("score_quality", "find_issues")
    graph.add_conditional_edges("find_issues", route_after_findings)
    graph.add_conditional_edges("write_recommendations", route_after_write)
    graph.add_conditional_edges("check_recommendations", route_after_check)
    graph.add_edge("save_quality", END)
    graph.add_edge("handle_error", END)
    return graph.compile(checkpointer=checkpointer)


@lru_cache
def get_interview_quality_graph() -> CompiledStateGraph:
    """The Interview Quality graph with PostgreSQL checkpoints, built once."""
    return build_interview_quality_graph(get_checkpointer())


def thread_id(session_id: int) -> str:
    """One thread per interview, started afresh for every check."""
    return f"interview-quality-{session_id}"
