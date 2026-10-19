"""Question bank suggestions: the interviewer's questions worth reusing.

Picked by rule: job-related questions (technical, behavioural or company)
that the candidate answered, and that make sense on their own, so not
follow-ups. Each one is compared with the question bank for the job's role
through the RAG MCP server's search_question_bank tool, and a question that
is already there, or very close to one that is, is left out.

Nothing is added here. The suggestions are saved with the assessment, and
only the questions the interviewer ticks are added to the question bank.
"""

import logging
import re

from app.core.logging import get_logger, log_event
from app.graphs.qa_analysis.segmentation import EVALUATED_KINDS
from app.mcp_clients import client as mcp_client

logger = get_logger(__name__)

# A question at least this similar to one in the bank is a duplicate.
DUPLICATE_SIMILARITY = 0.8


class QuestionBankSearchError(Exception):
    """The question bank could not be searched."""


def _plain(text: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", text.lower()).split())


def candidates(pairs: list[dict]) -> list[dict]:
    """The questions that could be reused, without repeats in the interview."""
    seen: set[str] = set()
    picked = []
    for pair in pairs:
        evaluation = pair.get("evaluation")
        if (
            pair["kind"] not in EVALUATED_KINDS
            or pair.get("follow_up_of")
            or evaluation is None
            or evaluation["answered"] == "not_answered"
        ):
            continue
        key = _plain(pair["question"])
        if key and key not in seen:
            seen.add(key)
            picked.append(pair)
    return picked


def in_bank(question: str, role: str) -> bool:
    """True when the question bank already has this question, or one very
    close to it, for the role."""
    try:
        result = mcp_client.call_tool(
            "rag", "search_question_bank", {"query": question, "role": role}
        )
    except Exception as exc:
        log_event(
            logger,
            "question_bank_search_failed",
            level=logging.WARNING,
            error_type=type(exc).__name__,
        )
        raise QuestionBankSearchError from exc
    if result.is_error:
        raise QuestionBankSearchError
    found = (result.structured_content or {}).get("result") or []
    return any(match["similarity"] >= DUPLICATE_SIMILARITY for match in found)


def suggest(pairs: list[dict], role: str) -> list[dict]:
    """The new questions to offer for the question bank, in the order asked.
    Raises QuestionBankSearchError when the bank cannot be searched."""
    return [
        {
            "pair_id": pair["id"],
            "question": pair["question"],
            "kind": pair["kind"],
            "added": False,
        }
        for pair in candidates(pairs)
        if not in_bank(pair["question"], role)
    ]
