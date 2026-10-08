"""LangGraph 2: CV Screening.

The main graph loads a job's CVs and sends each one down its own branch,
so the CVs are processed side by side and one bad file never stops the rest:

    start -> load_inputs -> screen_cv (one per CV) -> rank_candidates -> end

Each branch runs the per-CV pipeline:

    start        -> (must-haves met before) -> match_requirements
                 -> (parsed before)         -> check_must_haves
                 -> (new CV)                -> extract_text
    extract_text -> (text found)   -> parse_cv
                 -> (scanned PDF)  -> run_ocr -> (text found) -> parse_cv
                                              -> (unreadable) -> log_failure
                 -> (unreadable)   -> log_failure
    parse_cv     -> (facts read)   -> check_must_haves
                 -> (AI not available) -> log_failure
    check_must_haves -> (passed)           -> match_requirements
                     -> (missing must-have) -> exclude_candidate
                     -> (AI not available)  -> log_failure
    match_requirements -> (matched)          -> end of the steps built so far
                       -> (AI not available) -> log_failure

Later steps add the ATS score, scoring and ranking to this pipeline.
"""

import logging
import operator
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError
from app.core.logging import get_logger, log_event
from app.graphs.base import BaseState
from app.graphs.checkpointer import get_checkpointer
from app.graphs.screening import matching, must_haves, store
from app.graphs.screening.parsing import parse_cv
from app.services.text_extraction import extract_text, ocr_pdf

logger = get_logger(__name__)

# Below this many characters a file is treated as having no usable text.
MIN_TEXT_CHARS = 100

FILE_MISSING = "The CV file could not be found. Fetch the CVs again."
FILE_DAMAGED = "The CV file is damaged and could not be opened."
NO_TEXT = "No text could be read from the CV, even with OCR."
NO_TEXT_IN_FILE = "No text could be read from the CV file."
OCR_FAILED = "The scanned CV could not be read. Screen the CVs again to retry."
AI_UNAVAILABLE = "The AI service was not available. Screen the CVs again to retry."
UNEXPECTED = "The CV could not be processed because of an unexpected problem."


class CVState(TypedDict, total=False):
    """What is known about one CV as it moves through its branch."""

    candidate_id: int
    job_id: int
    cv_path: str
    text: str
    # How the text was read: "text" or "ocr".
    text_source: str
    # The structured facts read from the text (see app.schemas.cv.ParsedCV).
    parsed: dict
    # The job's requirements checklist, the same for every CV.
    requirements: dict
    # Why the candidate is excluded. Empty when the must-haves are met.
    exclusion: list[str]
    # True when an earlier run found the must-haves met.
    must_haves_met: bool
    # Per requirement: met, partially met or unmet, with CV evidence.
    matches: list[dict]
    # Set when the CV cannot be processed. The message is safe to show.
    failure: str


class ScreeningState(BaseState, total=False):
    job_id: int
    requirements: dict
    cvs: list[CVState]
    # One entry per CV, added by its branch as it finishes.
    outcomes: Annotated[list[dict], operator.add]
    summary: dict[str, int]


# --- Per-CV pipeline -------------------------------------------------------


def route_start(
    state: CVState,
) -> Literal["match_requirements", "check_must_haves", "extract_text"]:
    """A CV continues from the step it reached in an earlier run, so nothing
    is read, parsed or checked twice."""
    if state.get("must_haves_met"):
        return "match_requirements"
    return "check_must_haves" if state.get("parsed") else "extract_text"


def extract_text_node(state: CVState) -> dict:
    """Read the text that is stored in the file itself."""
    path = Path(state["cv_path"])
    if not path.exists():
        return {"failure": FILE_MISSING}
    try:
        text = extract_text(path.suffix.lower(), path.read_bytes())
    except Exception as exc:
        log_event(
            logger,
            "cv_text_extraction_failed",
            level=logging.WARNING,
            candidate_id=state["candidate_id"],
            error_type=type(exc).__name__,
        )
        return {"failure": FILE_DAMAGED}
    return {"text": text, "text_source": "text"}


def route_after_extract(state: CVState) -> Literal["parse_cv", "run_ocr", "log_failure"]:
    if state.get("failure"):
        return "log_failure"
    if len(state["text"]) >= MIN_TEXT_CHARS:
        return "parse_cv"
    # A PDF with almost no text is usually a scan. Other files have no
    # page images to read, so they cannot be recovered.
    if state["cv_path"].lower().endswith(".pdf"):
        return "run_ocr"
    return "log_failure"


def run_ocr(state: CVState) -> dict:
    """Read a scanned PDF by recognising the text in its page images."""
    try:
        content = Path(state["cv_path"]).read_bytes()
        text = ocr_pdf(content, get_settings().ocr_max_pages)
    except Exception as exc:
        log_event(
            logger,
            "cv_ocr_failed",
            level=logging.WARNING,
            candidate_id=state["candidate_id"],
            error_type=type(exc).__name__,
        )
        return {"text": "", "failure": OCR_FAILED}
    return {"text": text, "text_source": "ocr"}


def route_after_ocr(state: CVState) -> Literal["parse_cv", "log_failure"]:
    if state.get("failure") or len(state["text"]) < MIN_TEXT_CHARS:
        return "log_failure"
    return "parse_cv"


def parse_cv_node(state: CVState) -> dict:
    """Ask the AI to turn the CV text into structured facts, and keep them,
    so a later run can continue from here."""
    try:
        parsed = parse_cv(state["text"])
    except ServiceUnavailableError:
        return {"failure": AI_UNAVAILABLE}
    store.save_cv(state["candidate_id"], state["text"], state["text_source"], parsed)
    return {"parsed": parsed}


def route_after_parse(state: CVState) -> Literal["check_must_haves", "log_failure"]:
    return "log_failure" if state.get("failure") else "check_must_haves"


def check_must_haves_node(state: CVState) -> dict:
    """Check the minimum experience and every must-have requirement."""
    try:
        reasons = must_haves.check(state["requirements"], state["text"], state["parsed"])
    except ServiceUnavailableError:
        return {"failure": AI_UNAVAILABLE}
    if not reasons:
        store.save_passed(state["candidate_id"])
    return {"exclusion": reasons}


def route_after_check(
    state: CVState,
) -> Literal["exclude_candidate", "log_failure", "match_requirements"]:
    if state.get("failure"):
        return "log_failure"
    return "exclude_candidate" if state["exclusion"] else "match_requirements"


def match_requirements(state: CVState) -> dict:
    """Judge every requirement against the CV by meaning, with evidence."""
    try:
        matches = matching.match(
            state["candidate_id"], state["job_id"], state["requirements"], state
        )
    except ServiceUnavailableError:
        return {"failure": AI_UNAVAILABLE}
    store.save_matches(state["candidate_id"], matches)
    return {"matches": matches}


def route_after_match(state: CVState) -> Literal["log_failure", "__end__"]:
    return "log_failure" if state.get("failure") else END


def exclude_candidate(state: CVState) -> dict:
    """Record why the candidate is excluded. They are not matched or scored."""
    store.save_exclusion(state["candidate_id"], state["exclusion"])
    return {}


def log_failure(state: CVState) -> dict:
    """Record why this CV could not be processed. The batch carries on."""
    is_pdf = state["cv_path"].lower().endswith(".pdf")
    reason = state.get("failure") or (NO_TEXT if is_pdf else NO_TEXT_IN_FILE)
    store.save_failure(state["candidate_id"], reason)
    return {"failure": reason}


def build_cv_pipeline() -> CompiledStateGraph:
    """The steps one CV goes through."""
    graph = StateGraph(CVState)
    graph.add_node("extract_text", extract_text_node)
    graph.add_node("run_ocr", run_ocr)
    graph.add_node("parse_cv", parse_cv_node)
    graph.add_node("check_must_haves", check_must_haves_node)
    graph.add_node("exclude_candidate", exclude_candidate)
    graph.add_node("match_requirements", match_requirements)
    graph.add_node("log_failure", log_failure)

    graph.add_conditional_edges(START, route_start)
    graph.add_conditional_edges("extract_text", route_after_extract)
    graph.add_conditional_edges("run_ocr", route_after_ocr)
    graph.add_conditional_edges("parse_cv", route_after_parse)
    graph.add_conditional_edges("check_must_haves", route_after_check)
    graph.add_conditional_edges("match_requirements", route_after_match)
    graph.add_edge("exclude_candidate", END)
    graph.add_edge("log_failure", END)
    return graph.compile()


cv_pipeline = build_cv_pipeline()


# --- Main graph ------------------------------------------------------------


def load_inputs(state: ScreeningState) -> dict:
    """Find the job's CVs that are waiting, and the requirements to check."""
    job_id = state["job_id"]
    return {"cvs": store.load_cvs(job_id), "requirements": store.load_requirements(job_id)}


def send_each_cv(state: ScreeningState) -> list[Send] | Literal["rank_candidates"]:
    """Start one branch per CV, or go straight to the end if there are none."""
    if not state["cvs"]:
        return "rank_candidates"
    return [
        Send(
            "screen_cv",
            {**cv, "job_id": state["job_id"], "requirements": state["requirements"]},
        )
        for cv in state["cvs"]
    ]


def screen_cv(cv: CVState) -> dict:
    """Run one CV through its pipeline and report what happened.

    Any unexpected problem is caught here, so it is recorded against this
    CV only and the other branches are not affected.
    """
    candidate_id = cv["candidate_id"]
    was_read_before = bool(cv.get("parsed"))
    try:
        result = cv_pipeline.invoke(cv)
    except Exception as exc:
        log_event(
            logger,
            "cv_screening_failed",
            level=logging.ERROR,
            candidate_id=candidate_id,
            error_type=type(exc).__name__,
        )
        store.save_failure(candidate_id, UNEXPECTED)
        result = {"failure": UNEXPECTED}

    if result.get("failure"):
        outcome = "failed"
    elif result.get("exclusion"):
        outcome = "excluded"
    else:
        outcome = "passed"
    # How the text was read, only for CVs read successfully in this run.
    read_as = None if was_read_before or outcome == "failed" else result.get("text_source")
    return {
        "outcomes": [{"candidate_id": candidate_id, "outcome": outcome, "read_as": read_as}]
    }


def rank_candidates(state: ScreeningState) -> dict:
    """Where every branch meets again. For now it only counts the outcomes;
    ranking is added once the scoring steps exist."""
    outcomes = state.get("outcomes", [])
    results = [item["outcome"] for item in outcomes]
    read_as = [item["read_as"] for item in outcomes]
    return {
        "summary": {
            "total": len(outcomes),
            "read": read_as.count("text"),
            "read_by_ocr": read_as.count("ocr"),
            "passed": results.count("passed"),
            "excluded": results.count("excluded"),
            "failed": results.count("failed"),
        }
    }


def build_screening_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    graph = StateGraph(ScreeningState)
    graph.add_node("load_inputs", load_inputs)
    graph.add_node("screen_cv", screen_cv)
    graph.add_node("rank_candidates", rank_candidates)

    graph.add_edge(START, "load_inputs")
    graph.add_conditional_edges("load_inputs", send_each_cv, ["screen_cv", "rank_candidates"])
    graph.add_edge("screen_cv", "rank_candidates")
    graph.add_edge("rank_candidates", END)
    return graph.compile(checkpointer=checkpointer)


@lru_cache
def get_screening_graph() -> CompiledStateGraph:
    """The CV Screening graph with PostgreSQL checkpoints, built once."""
    return build_screening_graph(get_checkpointer())
