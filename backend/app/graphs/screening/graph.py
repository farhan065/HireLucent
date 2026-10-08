"""LangGraph 2: CV Screening.

The main graph loads a job's CVs and sends each one down its own branch,
so the CVs are processed side by side and one bad file never stops the rest:

    start -> load_inputs -> screen_cv (one per CV) -> rank_candidates -> end

Each branch runs the per-CV pipeline:

    extract_text -> (text found)   -> parse_cv
                 -> (scanned PDF)  -> run_ocr -> (text found) -> parse_cv
                                              -> (unreadable) -> log_failure
                 -> (unreadable)   -> log_failure
    parse_cv     -> (facts read)   -> end of the steps built so far
                 -> (AI not available) -> log_failure

Later steps add check_must_haves, match_requirements, scoring and ranking
to this pipeline.
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
from app.graphs.screening import store
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
    cv_path: str
    text: str
    # How the text was read: "text" or "ocr".
    text_source: str
    # The structured facts read from the text (see app.schemas.cv.ParsedCV).
    parsed: dict
    # Set when the CV cannot be processed. The message is safe to show.
    failure: str


class ScreeningState(BaseState, total=False):
    job_id: int
    cvs: list[CVState]
    # One entry per CV, added by its branch as it finishes.
    outcomes: Annotated[list[dict], operator.add]
    summary: dict[str, int]


# --- Per-CV pipeline -------------------------------------------------------


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
    """Ask the AI to turn the CV text into structured facts."""
    try:
        return {"parsed": parse_cv(state["text"])}
    except ServiceUnavailableError:
        return {"failure": AI_UNAVAILABLE}


def route_after_parse(state: CVState) -> Literal["log_failure", "__end__"]:
    return "log_failure" if state.get("failure") else END


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
    graph.add_node("log_failure", log_failure)

    graph.add_edge(START, "extract_text")
    graph.add_conditional_edges("extract_text", route_after_extract)
    graph.add_conditional_edges("run_ocr", route_after_ocr)
    graph.add_conditional_edges("parse_cv", route_after_parse)
    graph.add_edge("log_failure", END)
    return graph.compile()


cv_pipeline = build_cv_pipeline()


# --- Main graph ------------------------------------------------------------


def load_inputs(state: ScreeningState) -> dict:
    """Find the job's CVs that are waiting to be screened."""
    return {"cvs": store.load_cvs(state["job_id"])}


def send_each_cv(state: ScreeningState) -> list[Send] | Literal["rank_candidates"]:
    """Start one branch per CV, or go straight to the end if there are none."""
    if not state["cvs"]:
        return "rank_candidates"
    return [Send("screen_cv", cv) for cv in state["cvs"]]


def screen_cv(cv: CVState) -> dict:
    """Run one CV through its pipeline and report what happened.

    Any unexpected problem is caught here, so it is recorded against this
    CV only and the other branches are not affected.
    """
    candidate_id = cv["candidate_id"]
    try:
        result = cv_pipeline.invoke(cv)
        if not result.get("failure"):
            store.save_cv(
                candidate_id, result["text"], result["text_source"], result["parsed"]
            )
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

    outcome = "failed" if result.get("failure") else result["text_source"]
    return {"outcomes": [{"candidate_id": candidate_id, "outcome": outcome}]}


def rank_candidates(state: ScreeningState) -> dict:
    """Where every branch meets again. For now it only counts the outcomes;
    ranking is added once the scoring steps exist."""
    outcomes = [item["outcome"] for item in state.get("outcomes", [])]
    return {
        "summary": {
            "total": len(outcomes),
            "read": outcomes.count("text"),
            "read_by_ocr": outcomes.count("ocr"),
            "failed": outcomes.count("failed"),
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
