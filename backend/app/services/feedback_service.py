"""FeedbackService: the interviewer's decision and the candidate's feedback
email (innovation feature F11, Candidate Feedback Composer).

Who gets which email:
- not shortlisted after screening (scored, excluded, or CV not readable):
  rejected at screening. They can still be shortlisted until their email is
  sent; then the shortlist is locked for them.
- after the interview, with an approved report: Hire or Reject, decided by
  the interviewer row by row or by a rule. A decision can change until its
  email is sent.

Emails are written by LangGraph 5 (graphs/feedback), one candidate at a
time in a background task, and wait as drafts. Nothing is sent until the
interviewer approves a draft, one by one or with Send all passed (drafts
with fairness warnings are left for one-by-one review).
"""

from datetime import datetime, timezone

from fastapi import BackgroundTasks
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.core.errors import AppError, ConflictError, NotFoundError, ServiceUnavailableError
from app.core.logging import get_logger, log_event
from app.graphs.base import thread_config
from app.graphs.checkpointer import get_checkpointer
from app.graphs.feedback import graph as feedback_graph
from app.graphs.feedback import store as feedback_store
from app.graphs.feedback import templates
from app.models import Assessment, Candidate, CandidateFeedback, Job, Task
from app.models.enums import AssessmentStatus, CandidateStatus, FeedbackStatus
from app.schemas.feedback import DecisionRule, FeedbackReview
from app.services import evaluation_service, task_service
from app.services.task_service import ACTIVE, TaskProgress

logger = get_logger(__name__)

WRITING = task_service.FEEDBACK_WRITING
SENDING = task_service.FEEDBACK_SENDING
KINDS = (WRITING, SENDING)

BUSY = "Feedback emails are being written or sent. Wait for it to finish."
NOT_FOUND = "This candidate does not exist."
NOT_IN_JOB = "Some of these candidates are not part of this job."
NO_REPORT = "Approve the candidate's report before deciding."
LOCKED = "The candidate's email is already sent, so the decision cannot change."
NOT_ELIGIBLE = "Some of these candidates cannot get a feedback email now."
NOTHING_TO_WRITE = "Every chosen candidate already has an email."
NO_EMAIL = "This candidate has no feedback email yet."
NOT_WAITING = "This email is not waiting for review."
HAS_WARNINGS = (
    "This email still has fairness warnings. Fix them, or choose Send anyway."
)
FIXED_MESSAGE = "This is a fixed message. Edit it instead of asking for changes."
NOTHING_TO_SEND = "No email is ready to send. Drafts with warnings are sent one by one."
REWRITE_FAILED = (
    "The AI service was not available, so the email was not rewritten. "
    "The draft is unchanged; try again in a moment."
)

SCREENING = "screening"
INTERVIEW = "interview"
DRAFT_STATUSES = (FeedbackStatus.WAITING_REVIEW, FeedbackStatus.FAILED)


class FeedbackFailed(AppError):
    """No email could be written or sent. The message is safe to show."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_feedback_graph() -> CompiledStateGraph:
    return feedback_graph.get_feedback_graph()


def _candidate(db: Session, candidate_id: int) -> Candidate:
    candidate = db.get(Candidate, candidate_id)
    if candidate is None:
        raise NotFoundError(NOT_FOUND)
    return candidate


def _ensure_no_feedback_task(db: Session) -> None:
    if db.scalar(select(Task.id).where(Task.kind.in_(KINDS), Task.status.in_(ACTIVE)).limit(1)):
        raise ConflictError(BUSY)


def stage_of(candidate: Candidate) -> str | None:
    """screening for someone not shortlisted, interview for someone decided
    after the interview, otherwise None."""
    if candidate.status in feedback_store.SCREENING_REJECTED:
        return SCREENING
    if candidate.status == CandidateStatus.ASSESSED and candidate.decision:
        return INTERVIEW
    return None


def drop_unsent_email(db: Session, candidate: Candidate) -> None:
    """Remove an email that is not sent yet, for example when the candidate
    is shortlisted or their decision changes. A sent email always stays."""
    feedback = candidate.feedback
    if feedback is None or candidate.feedback_sent:
        return
    db.delete(feedback)
    db.flush()
    get_checkpointer().delete_thread(feedback_graph.thread_id(candidate.id))


# --- Decisions after the interview -------------------------------------------


def _approved(db: Session, candidate_id: int) -> bool:
    return (
        db.scalar(
            select(Assessment.id)
            .where(
                Assessment.candidate_id == candidate_id,
                Assessment.status == AssessmentStatus.APPROVED,
            )
            .limit(1)
        )
        is not None
    )


def set_decision(db: Session, candidate_id: int, decision: str | None, user_id: int) -> Candidate:
    """Hire or reject a candidate whose report is approved, or take the
    decision back. Locked once the email is sent; an email not sent yet
    is removed, because it was written for the old decision."""
    candidate = _candidate(db, candidate_id)
    if candidate.feedback_sent:
        raise ConflictError(LOCKED)
    if not _approved(db, candidate_id):
        raise ConflictError(NO_REPORT)
    if decision != candidate.decision:
        drop_unsent_email(db, candidate)
        candidate.decision = decision
        candidate.decided_by = user_id if decision else None
        candidate.decided_at = _now() if decision else None
    db.commit()
    log_event(logger, "decision_set", candidate_id=candidate_id, decision=decision)
    return candidate


def decide_by_rule(db: Session, job_id: int, rule: DecisionRule, user_id: int) -> dict:
    """Hire the top N ranked candidates, or everyone with at least an overall
    score, and reject the other ranked ones. Only approved reports count;
    candidates whose email is sent keep their decision."""
    rows = [
        row
        for row in evaluation_service.ranked_assessments(db, job_id)
        if row["rank"] is not None and row["status"] == AssessmentStatus.APPROVED
    ]
    hired = rejected = skipped = 0
    for position, row in enumerate(rows):
        hire = position < rule.top if rule.top is not None else row["overall_score"] >= rule.min_score
        candidate = _candidate(db, row["candidate_id"])
        if candidate.feedback_sent:
            skipped += 1
            continue
        decision = "hire" if hire else "reject"
        if candidate.decision != decision:
            drop_unsent_email(db, candidate)
            candidate.decision = decision
            candidate.decided_by = user_id
            candidate.decided_at = _now()
        hired += hire
        rejected += not hire
    db.commit()
    log_event(
        logger, "decisions_applied", job_id=job_id, hired=hired, rejected=rejected, skipped=skipped
    )
    return {"hired": hired, "rejected": rejected, "skipped": skipped}


# --- Writing emails -----------------------------------------------------------


def start_writing(
    db: Session,
    background_tasks: BackgroundTasks,
    graph: CompiledStateGraph,
    job_id: int,
    candidate_ids: list[int],
    user_id: int,
) -> Task:
    """Write the email of every chosen candidate who has none yet (or whose
    draft was discarded), one after another in the background."""
    if db.get(Job, job_id) is None:
        raise NotFoundError("This job does not exist.")
    _ensure_no_feedback_task(db)
    to_write = []
    for candidate_id in dict.fromkeys(candidate_ids):
        candidate = _candidate(db, candidate_id)
        if candidate.job_id != job_id:
            raise AppError(NOT_IN_JOB)
        if stage_of(candidate) is None:
            raise ConflictError(NOT_ELIGIBLE)
        if candidate.feedback is None or candidate.feedback_status == FeedbackStatus.DISCARDED:
            to_write.append(candidate_id)
    if not to_write:
        raise ConflictError(NOTHING_TO_WRITE)
    return task_service.start_task(
        db,
        background_tasks,
        WRITING,
        user_id,
        lambda progress: run_writing(graph, to_write, progress),
        job_id=job_id,
    )


def run_writing(graph: CompiledStateGraph, candidate_ids: list[int], progress: TaskProgress) -> dict:
    """Write the emails one by one. One that fails does not stop the
    others; if all fail, the task fails with the reason."""
    total = len(candidate_ids)
    written, failures = 0, []
    for done, candidate_id in enumerate(candidate_ids):
        progress.note({"candidate_ids": candidate_ids, "current": candidate_id, "failures": failures})
        progress.update(done, total, f"Writing emails · {done + 1} of {total}")
        config = thread_config(feedback_graph.thread_id(candidate_id))
        if graph.checkpointer is not None:
            graph.checkpointer.delete_thread(config["configurable"]["thread_id"])
        # Background work: its AI calls leave room for the AI Agent and the room.
        with ai_client.background_calls():
            graph.invoke({"candidate_id": candidate_id}, config)
        failure = graph.get_state(config).values.get("failure")
        if failure:
            failures.append({"candidate_id": candidate_id, "reason": failure})
        else:
            written += 1
    progress.note({"candidate_ids": candidate_ids, "current": None, "failures": failures})
    progress.update(total, total, f"Wrote {written} of {total} emails")
    log_event(logger, "feedback_writing_finished", total=total, written=written, failed=len(failures))
    if not written:
        raise FeedbackFailed(failures[-1]["reason"])
    return {
        "total": total,
        "written": written,
        "failed": len(failures),
        "candidate_ids": candidate_ids,
        "failures": failures,
    }


# --- Reading and reviewing ----------------------------------------------------


def get_feedback(db: Session, candidate_id: int) -> CandidateFeedback:
    candidate = _candidate(db, candidate_id)
    if candidate.feedback is None:
        raise NotFoundError(NO_EMAIL)
    return candidate.feedback


def review(
    db: Session,
    graph: CompiledStateGraph,
    candidate_id: int,
    payload: FeedbackReview,
    user_id: int,
) -> CandidateFeedback:
    """Continue the paused email with the interviewer's review: approve
    (send), send anyway with warnings, edit the text, ask the AI for changes
    with a note, or discard it. Returns the email as it is afterwards."""
    feedback = get_feedback(db, candidate_id)
    config = thread_config(feedback_graph.thread_id(candidate_id))
    if feedback.status not in DRAFT_STATUSES or not feedback_graph.is_waiting_for_review(
        graph, config
    ):
        raise ConflictError(NOT_WAITING)
    if payload.action == "approve" and feedback.warnings:
        raise ConflictError(HAS_WARNINGS)
    if payload.action == "request_changes" and feedback.kind not in templates.AI_KINDS:
        raise ConflictError(FIXED_MESSAGE)
    if stage_of(feedback.candidate) is None:
        raise ConflictError(NOT_ELIGIBLE)

    graph.invoke(Command(resume={**payload.model_dump(), "user_id": user_id}), config)
    if graph.get_state(config).values.get("revision_failed"):
        raise ServiceUnavailableError(REWRITE_FAILED)
    log_event(logger, "feedback_reviewed", candidate_id=candidate_id, action=payload.action)
    db.expire_all()
    return get_feedback(db, candidate_id)


def _ready_to_send(db: Session, job_id: int, stage: str) -> list[int]:
    """The job's drafts in this stage that passed every check."""
    rows = db.scalars(
        select(CandidateFeedback).where(
            CandidateFeedback.job_id == job_id,
            CandidateFeedback.status == FeedbackStatus.WAITING_REVIEW,
        )
    ).all()
    return [
        row.candidate_id
        for row in rows
        if not row.warnings and stage_of(row.candidate) == stage
    ]


def start_sending(
    db: Session,
    background_tasks: BackgroundTasks,
    graph: CompiledStateGraph,
    job_id: int,
    stage: str,
    user_id: int,
) -> Task:
    """Send all passed drafts of one stage, one after another in the
    background, as if each were approved one by one."""
    if db.get(Job, job_id) is None:
        raise NotFoundError("This job does not exist.")
    _ensure_no_feedback_task(db)
    candidate_ids = _ready_to_send(db, job_id, stage)
    if not candidate_ids:
        raise ConflictError(NOTHING_TO_SEND)
    return task_service.start_task(
        db,
        background_tasks,
        SENDING,
        user_id,
        lambda progress: run_sending(graph, candidate_ids, user_id, progress),
        job_id=job_id,
    )


def run_sending(
    graph: CompiledStateGraph, candidate_ids: list[int], user_id: int, progress: TaskProgress
) -> dict:
    total = len(candidate_ids)
    sent, failures = 0, []
    for done, candidate_id in enumerate(candidate_ids):
        progress.note({"candidate_ids": candidate_ids, "current": candidate_id, "failures": failures})
        progress.update(done, total, f"Sending {done + 1} of {total}")
        config = thread_config(feedback_graph.thread_id(candidate_id))
        if not feedback_graph.is_waiting_for_review(graph, config):
            failures.append({"candidate_id": candidate_id, "reason": NOT_WAITING})
            continue
        graph.invoke(Command(resume={"action": "approve", "user_id": user_id}), config)
        error = graph.get_state(config).values.get("send_error")
        if error:
            failures.append({"candidate_id": candidate_id, "reason": error})
        else:
            sent += 1
    progress.note({"candidate_ids": candidate_ids, "current": None, "failures": failures})
    progress.update(total, total, f"Sent {sent} of {total} emails")
    log_event(logger, "feedback_sending_finished", total=total, sent=sent, failed=len(failures))
    if not sent:
        raise FeedbackFailed(failures[-1]["reason"])
    return {
        "total": total,
        "sent": sent,
        "failed": len(failures),
        "candidate_ids": candidate_ids,
        "failures": failures,
    }


def activity(db: Session, job_id: int) -> dict:
    """The writing or sending running for the job, the last finished one, and
    how many emails are still to send in each stage."""
    if db.get(Job, job_id) is None:
        raise NotFoundError("This job does not exist.")
    running = db.scalar(
        select(Task)
        .where(Task.job_id == job_id, Task.kind.in_(KINDS), Task.status.in_(ACTIVE))
        .limit(1)
    )
    last = db.scalar(
        select(Task)
        .where(Task.job_id == job_id, Task.kind.in_(KINDS), Task.status.not_in(ACTIVE))
        .order_by(Task.created_at.desc())
        .limit(1)
    )
    candidates = db.scalars(select(Candidate).where(Candidate.job_id == job_id)).all()
    counts = {SCREENING: 0, INTERVIEW: 0}
    for candidate in candidates:
        stage = stage_of(candidate)
        if stage and not candidate.feedback_sent:
            counts[stage] += 1
    return {
        "running": running,
        "last": last,
        "screening_to_send": counts[SCREENING],
        "interview_to_send": counts[INTERVIEW],
    }
