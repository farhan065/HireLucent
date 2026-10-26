"""Token usage of every chat model answer, for the AI cost report.

One JSON line per answer goes to logs/ai_usage.log: when, which API route
and graph step asked, the job, candidate or interview IDs, and the token
counts the provider sent back. Prompts and answers are never written.

The file is kept apart from the rotating application log, so the history is
not deleted as the log grows. scripts/ai_cost_report.py turns it into CSV
files.
"""

import json
import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from app.core.config import get_settings
from app.core.logging import get_logger, log_event

logger = get_logger(__name__)

# Tags for the model calls made in the current request or background task:
# route, graph, step, job_id, candidate_id, session_id, attempt.
_tags: ContextVar[dict[str, Any] | None] = ContextVar("ai_usage_tags", default=None)

_write_lock = Lock()

# Number IDs and UUIDs in a path become {id}, so all jobs share one route.
_ID_SEGMENT = re.compile(
    r"/(\d+|[0-9a-fA-F]{32}|[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})(?=/|$)"
)

# Each graph runs on a thread named after what it works on, so the thread
# tells which graph made a call and for which candidate or interview.
_THREADS = (
    (re.compile(r"^screening-"), "screening", None),
    (re.compile(r"^evaluation-.+-(\d+)$"), "qa_analysis", "session_id"),
    (re.compile(r"^final-assessment-(\d+)$"), "final_assessment", "session_id"),
    (re.compile(r"^cv-claims-(\d+)$"), "final_assessment", "session_id"),
    (re.compile(r"^interview-quality-(\d+)$"), "interview_quality", "session_id"),
    (re.compile(r"^feedback-(\d+)$"), "feedback", "candidate_id"),
    (re.compile(r"^interview-(\d+)$"), "interview_room", "session_id"),
)


@contextmanager
def usage_context(**tags: Any) -> Iterator[None]:
    """Tag the model calls made inside this block, for example with
    candidate_id=12. Tags set to None are left out; inner blocks win."""
    current = _tags.get() or {}
    token = _tags.set({**current, **{k: v for k, v in tags.items() if v is not None}})
    try:
        yield
    finally:
        _tags.reset(token)


def route_label(method: str, path: str) -> str:
    """The route of a request with its IDs replaced, e.g. POST /jobs/{id}/screen."""
    return f"{method} {_ID_SEGMENT.sub('/{id}', path)}"


def _from_thread(thread_id: Any) -> dict[str, Any]:
    """The graph and the ID that a graph's thread name carries."""
    if not isinstance(thread_id, str):
        return {}
    for pattern, graph, id_name in _THREADS:
        match = pattern.match(thread_id)
        if match:
            found = {"graph": graph}
            if id_name:
                found[id_name] = int(match.group(1))
            return found
    # The AI Agent's conversations have random thread names.
    return {"graph": "recruiter"}


def _token_counts(response: LLMResult) -> dict[str, int] | None:
    """The token counts of an answer, as the provider reported them."""
    for generations in response.generations:
        for generation in generations:
            usage = getattr(getattr(generation, "message", None), "usage_metadata", None)
            if usage:
                details = usage.get("output_token_details") or {}
                return {
                    "input_tokens": int(usage.get("input_tokens") or 0),
                    "output_tokens": int(usage.get("output_tokens") or 0),
                    "thinking_tokens": int(details.get("reasoning") or 0),
                }
    return None


# The job (and candidate) of each interview or candidate already looked up.
# They never change, so each is read from the database only once.
_known_jobs: dict[tuple[str, int], tuple[int | None, int]] = {}


def find_job(candidate_id: int | None, session_id: int | None) -> tuple[int | None, int | None]:
    """The candidate and job of an interview, or the job of a candidate,
    read from the database when the call is made. Recording the job then
    keeps the call counted for its job even if the candidate or interview
    is deleted later."""
    key = ("session", session_id) if session_id else ("candidate", candidate_id)
    if key[1] is None:
        return candidate_id, None
    if key not in _known_jobs:
        from sqlalchemy import select

        from app.db.session import SessionLocal
        from app.models import Candidate, InterviewSession

        try:
            with SessionLocal() as db:
                if session_id:
                    row = db.execute(
                        select(InterviewSession.candidate_id, InterviewSession.job_id).where(
                            InterviewSession.id == session_id
                        )
                    ).first()
                else:
                    job_id = db.scalar(select(Candidate.job_id).where(Candidate.id == candidate_id))
                    row = (candidate_id, job_id) if job_id is not None else None
        except Exception as exc:
            log_event(
                logger,
                "ai_usage_job_not_found",
                level=logging.WARNING,
                error_type=type(exc).__name__,
            )
            return candidate_id, None
        if row is None:
            return candidate_id, None
        _known_jobs[key] = (row[0], row[1])
    found_candidate, job_id = _known_jobs[key]
    return candidate_id or found_candidate, job_id


def usage_record(metadata: dict[str, Any], counts: dict[str, int], model: str) -> dict[str, Any]:
    """One line of the usage file. Only names, IDs and counts."""
    tags = _tags.get() or {}
    found = _from_thread(metadata.get("thread_id"))
    graph = tags.get("graph") or found.get("graph", "")
    candidate_id = tags.get("candidate_id") or found.get("candidate_id")
    session_id = tags.get("session_id") or found.get("session_id")
    job_id = tags.get("job_id")
    if job_id is None and (candidate_id or session_id):
        candidate_id, job_id = find_job(candidate_id, session_id)
    record = {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "route": tags.get("route", ""),
        "graph": graph,
        "step": tags.get("step") or metadata.get("langgraph_node", ""),
        "model": model,
        "job_id": job_id,
        "candidate_id": candidate_id,
        "session_id": session_id,
        "attempt": tags.get("attempt", 1),
        **counts,
    }
    if graph == "recruiter":
        # The AI Agent conversation (a random code). The report finds the job
        # the conversation saved, so the chat before saving counts for it too.
        record["chat_thread"] = metadata.get("thread_id")
    return record


def write_record(record: dict[str, Any]) -> None:
    """Add one line to the usage file. A failure is logged, never raised,
    so counting can never stop an AI call."""
    settings = get_settings()
    path = Path(settings.log_dir) / settings.ai_usage_file_name
    try:
        with _write_lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(record) + "\n")
    except OSError as exc:
        log_event(
            logger, "ai_usage_not_written", level=logging.WARNING, error_type=type(exc).__name__
        )


class UsageRecorder(BaseCallbackHandler):
    """Writes one usage line for each answer from the chat model."""

    def __init__(self, model: str) -> None:
        self.model = model
        # The graph metadata of each call, from its start until its end.
        self._calls: dict[UUID, dict[str, Any]] = {}

    def on_chat_model_start(
        self,
        serialized: dict,
        messages: list,
        *,
        run_id: UUID,
        metadata: dict | None = None,
        **kwargs: Any,
    ) -> None:
        self._calls[run_id] = dict(metadata or {})

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, **kwargs: Any) -> None:
        metadata = self._calls.pop(run_id, {})
        counts = _token_counts(response)
        if counts is not None:
            write_record(usage_record(metadata, counts, self.model))

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        # No answer, so no tokens to count (the provider does not bill it).
        self._calls.pop(run_id, None)
