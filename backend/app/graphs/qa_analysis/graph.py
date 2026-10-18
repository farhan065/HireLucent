"""LangGraph 3: Q&A Analysis.

Turns one interview's transcript into evaluated question-answer pairs:

    start -> load_transcript -> (transcript ready)   -> segment_qa
                             -> (transcript missing) -> handle_error -> end
    segment_qa -> (pairs found)    -> classify_question
               -> (no valid pairs, attempts left) -> segment_qa
               -> (AI not available, or still no pairs) -> handle_error -> end
    classify_question -> small talk is skipped; job-related answers go in
                         batches, one branch each (Send) -> evaluate_answers
                      -> (nothing to send to the AI) -> collect_evaluations
    evaluate_answers  -> collect_evaluations
    collect_evaluations -> (every batch judged) -> save_analysis -> end
                        -> (a batch failed)     -> handle_error -> end

Each evaluate_answers branch runs its own small pipeline:

    start -> (technical or company answers) -> retrieve_references
          -> (behavioural answers only)     -> judge_batch
    retrieve_references -> (searched)                   -> judge_batch
                        -> (Knowledge Base not reached) -> end (failed)
    judge_batch -> (valid)                                -> end
                -> (fails the checks, attempts left)      -> judge_batch
                -> (AI not available, or still invalid)   -> end (failed)

retrieve_references finds approved Knowledge Base passages for each
technical and company answer, and judge_batch checks accuracy against them
first. With no usable reference, a technical answer's accuracy is the AI
interviewer's own judgement, and a company answer's accuracy is not scored,
because the AI cannot know the company's own facts. The evaluation says
which it was. Mapping the job's requirements follows in a later step.
"""

import logging
import operator
from functools import lru_cache
from typing import Annotated, Literal, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from app.core.errors import ServiceUnavailableError
from app.core.logging import get_logger, log_event
from app.graphs.base import BaseState, can_retry
from app.graphs.checkpointer import get_checkpointer
from app.graphs.qa_analysis import evaluation, references, segmentation, store
from app.models.enums import SessionStatus

logger = get_logger(__name__)

NOT_FOUND = "This interview no longer exists."
NOT_COMPLETED = "Only a completed interview can be evaluated."
NO_TRANSCRIPT = "This interview has no transcript with both people speaking."
AI_UNAVAILABLE = "The AI service was not available. Evaluate the interview again to retry."
NO_PAIRS = "No questions and answers could be found in the transcript."
INVALID_EVALUATION = (
    "The AI could not give a valid evaluation of every answer. "
    "Evaluate the interview again to retry."
)
NO_KNOWLEDGE_BASE = (
    "The Knowledge Base could not be searched for references. "
    "Evaluate the interview again to retry."
)


class QAState(BaseState, total=False):
    session_id: int
    candidate_id: int
    job_title: str
    # The transcript turns: id, speaker, start_ms, end_ms and text.
    turns: list[dict]
    # The question-answer pairs (see segmentation.build_pairs), each with its
    # evaluation once collect_evaluations has run.
    pairs: list[dict]
    # Added by each evaluate_answers branch as it finishes.
    evaluations: Annotated[list[dict], operator.add]
    batch_failures: Annotated[list[str], operator.add]
    # Set when the analysis cannot be done. The message is safe to show.
    failure: str


class BatchState(TypedDict, total=False):
    """One batch of pairs on its way through evaluate_answers."""

    session_id: int
    job_title: str
    batch: list[dict]
    # Only the turns this batch needs.
    turns: list[dict]
    # Reference passages for each technical pair, by pair id.
    references: dict[str, list[dict]]
    attempts: int
    evaluations: list[dict]
    problems: list[str]
    failure: str


# --- Per-batch pipeline ------------------------------------------------------


def _turns(state: BatchState) -> dict[int, dict]:
    return {turn["id"]: turn for turn in state["turns"]}


def route_start(state: BatchState) -> Literal["retrieve_references", "judge_batch"]:
    """Only technical and company answers are checked against references."""
    if any(pair["kind"] in evaluation.CHECKED_KINDS for pair in state["batch"]):
        return "retrieve_references"
    return "judge_batch"


def retrieve_references(state: BatchState) -> dict:
    """Find approved Knowledge Base passages for each technical answer,
    through the RAG MCP server."""
    try:
        found = references.for_batch(state["batch"], _turns(state))
    except references.ReferenceSearchError:
        return {"failure": NO_KNOWLEDGE_BASE}
    log_event(
        logger,
        "qa_references_found",
        session_id=state["session_id"],
        answers=len(found),
        with_references=sum(bool(passages) for passages in found.values()),
    )
    return {"references": found}


def route_after_retrieve(state: BatchState) -> Literal["judge_batch", "__end__"]:
    return END if state.get("failure") else "judge_batch"


def judge_batch(state: BatchState) -> dict:
    """Ask the AI to judge the batch, then check its answer."""
    attempts = state.get("attempts", 0) + 1
    turns = _turns(state)
    found_references = state.get("references", {})
    try:
        answer = evaluation.ask_ai(state["job_title"], state["batch"], turns, found_references)
    except ServiceUnavailableError:
        return {"failure": AI_UNAVAILABLE, "attempts": attempts}
    found = evaluation.problems(answer, state["batch"], turns, found_references)
    if found:
        log_event(
            logger,
            "qa_evaluation_invalid",
            level=logging.WARNING,
            session_id=state["session_id"],
            attempt=attempts,
            problems=sorted(set(found)),
        )
        return {"problems": found, "attempts": attempts}
    return {
        "evaluations": evaluation.to_evaluations(
            answer, state["batch"], turns, found_references
        ),
        "problems": [],
        "attempts": attempts,
    }


def route_after_judge(state: BatchState) -> Literal["judge_batch", "__end__"]:
    """An answer that failed the checks is asked for again while attempts
    are left."""
    if state.get("problems") and not state.get("failure") and can_retry(state):
        return "judge_batch"
    return END


def build_batch_pipeline() -> CompiledStateGraph:
    graph = StateGraph(BatchState)
    graph.add_node("retrieve_references", retrieve_references)
    graph.add_node("judge_batch", judge_batch)
    graph.add_conditional_edges(START, route_start)
    graph.add_conditional_edges("retrieve_references", route_after_retrieve)
    graph.add_conditional_edges("judge_batch", route_after_judge)
    return graph.compile()


batch_pipeline = build_batch_pipeline()


# --- Main graph --------------------------------------------------------------


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


def classify_question(state: QAState) -> list[Send] | Literal["collect_evaluations"]:
    """Route each pair by its kind (rule-based, the kind came with the pair):
    small talk is not evaluated, and job-related answers are sent to the AI
    in batches, one branch per batch."""
    turns_by_id = {turn["id"]: turn for turn in state["turns"]}
    sends = []
    for batch in evaluation.make_batches(state["pairs"]):
        needed = {
            n for pair in batch for n in pair["question_turn_ids"] + pair["answer_turn_ids"]
        }
        sends.append(
            Send(
                "evaluate_answers",
                {
                    "session_id": state["session_id"],
                    "job_title": state["job_title"],
                    "batch": batch,
                    "turns": [turns_by_id[n] for n in sorted(needed)],
                },
            )
        )
    return sends or "collect_evaluations"


def route_after_segment(
    state: QAState,
) -> list[Send] | Literal["collect_evaluations", "segment_qa", "handle_error"]:
    if state.get("failure"):
        return "handle_error"
    if state["pairs"]:
        return classify_question(state)
    return "segment_qa" if can_retry(state) else "handle_error"


def evaluate_answers(batch: BatchState) -> dict:
    """Judge one batch through its pipeline and report the result."""
    result = batch_pipeline.invoke(batch)
    if result.get("failure"):
        return {"batch_failures": [result["failure"]]}
    if result.get("problems"):
        return {"batch_failures": [INVALID_EVALUATION]}
    return {"evaluations": result["evaluations"]}


def collect_evaluations(state: QAState) -> dict:
    """Where every branch meets again. Each pair gets its evaluation; a
    job-related question with no answer gets the no-answer evaluation."""
    if state.get("batch_failures"):
        return {"failure": state["batch_failures"][0]}
    return {"pairs": evaluation.attach(state["pairs"], state.get("evaluations", []))}


def route_after_collect(state: QAState) -> Literal["save_analysis", "handle_error"]:
    return "handle_error" if state.get("failure") else "save_analysis"


def save_analysis(state: QAState) -> dict:
    """Keep the evaluated pairs on the interview's assessment."""
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
    graph.add_node("evaluate_answers", evaluate_answers)
    graph.add_node("collect_evaluations", collect_evaluations)
    graph.add_node("save_analysis", save_analysis)
    graph.add_node("handle_error", handle_error)

    graph.add_edge(START, "load_transcript")
    graph.add_conditional_edges("load_transcript", route_after_load)
    graph.add_conditional_edges(
        "segment_qa",
        route_after_segment,
        ["evaluate_answers", "collect_evaluations", "segment_qa", "handle_error"],
    )
    graph.add_edge("evaluate_answers", "collect_evaluations")
    graph.add_conditional_edges("collect_evaluations", route_after_collect)
    graph.add_edge("save_analysis", END)
    graph.add_edge("handle_error", END)
    return graph.compile(checkpointer=checkpointer)


@lru_cache
def get_qa_analysis_graph() -> CompiledStateGraph:
    """The Q&A Analysis graph with PostgreSQL checkpoints, built once."""
    return build_qa_analysis_graph(get_checkpointer())


def answers_to_judge(pairs: list[dict]) -> int:
    """How many answers the AI will judge, for the progress shown."""
    return sum(len(batch) for batch in evaluation.make_batches(pairs))
