"""Reference retrieval: approved Knowledge Base passages for checking the
accuracy of technical and company answers.

For each technical or company pair, the question and the candidate's answer
are sent to the RAG MCP server's verify_answer tool, which searches only the
documents uploaded as references. The passages it returns are given to the
AI with the answer, so accuracy is checked against approved material first.
Contact details are masked before the answer leaves the backend.
"""

import logging

from app.core.logging import get_logger, log_event
from app.graphs.qa_analysis.evaluation import CHECKED_KINDS
from app.graphs.qa_analysis.segmentation import mask_text
from app.mcp_clients import client as mcp_client

logger = get_logger(__name__)

# The answer is cut to this before it is sent for the search.
MAX_ANSWER_CHARS = 1500


class ReferenceSearchError(Exception):
    """The Knowledge Base could not be searched."""


def search(question: str, answer: str) -> list[dict]:
    """The reference passages for one question and answer, closest first."""
    try:
        result = mcp_client.call_tool(
            "rag", "verify_answer", {"question": question, "answer": answer}
        )
    except Exception as exc:
        log_event(
            logger,
            "reference_search_failed",
            level=logging.WARNING,
            error_type=type(exc).__name__,
        )
        raise ReferenceSearchError from exc
    if result.is_error:
        log_event(logger, "reference_search_failed", level=logging.WARNING, error_type="tool")
        raise ReferenceSearchError
    return (result.structured_content or {}).get("result") or []


def for_batch(batch: list[dict], turns: dict[int, dict]) -> dict[str, list[dict]]:
    """The reference passages for each technical or company pair of a batch,
    by pair id. Behavioural answers are not checked against references."""
    references: dict[str, list[dict]] = {}
    for pair in batch:
        if pair["kind"] not in CHECKED_KINDS:
            continue
        answer = " ".join(mask_text(turns[n]["text"]) for n in pair["answer_turn_ids"])
        references[pair["id"]] = search(pair["question"], answer[:MAX_ANSWER_CHARS])
    return references
