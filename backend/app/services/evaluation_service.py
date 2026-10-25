"""EvaluationService: evaluates completed interviews in the background.

The interviewer asks for an evaluation, either for one interview or for all
of a job's completed interviews that have not been evaluated yet. Each
interview runs through the Q&A Analysis graph, which finds the questions and
answers and evaluates each answer, then through the Final Assessment graph,
which writes the report and pauses it as a draft. The interviewer then
approves the draft, asks for changes or edits it (review_assessment).

The Final Assessment graph also compares the CV's claims with the interview
(F8) before it writes the report. An interview evaluated before that, or
whose claims could not be checked because the AI was down, can have its
claims checked on their own (start_claim_check), and the interviewer marks
each contradiction or unverified claim as checked or dismissed
(review_claim).

After the report, the Interview Quality graph (F10) looks at how the
interview itself was run: the questions, the requirements they explored and
the speaking time, with recommendations for the next interview. Its result
never changes a score or the report, and an interview evaluated before F10
can be checked on its own (start_quality_check). interview_consistency
compares the job's checked interviews with each other.

Only one evaluation runs at a time, because the AI's per-minute limit is
shared. An evaluation does not block fetching or screening CVs for the job.
While it runs, its task keeps which interviews it covers, which one it is on
and which failed, so the screens can show this after a page reload.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import BackgroundTasks
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from sqlalchemy import exists, select
from sqlalchemy.orm import Session, selectinload

from app.ai import client as ai_client
from app.core.config import get_settings
from app.core.errors import AppError, ConflictError, NotFoundError, ServiceUnavailableError
from app.core.logging import get_logger, log_event
from app.graphs.base import thread_config
from app.graphs.final_assessment import claims as cv_claims
from app.graphs.final_assessment import graph as final_graph
from app.graphs.final_assessment import scoring
from app.graphs.interview_quality import consistency
from app.graphs.interview_quality import graph as quality_graph
from app.graphs.qa_analysis import coverage as coverage_rules
from app.graphs.qa_analysis.graph import answers_to_judge, get_qa_analysis_graph
from app.models import Assessment, Candidate, InterviewSession, Job, Task, TranscriptTurn, User
from app.models.enums import AssessmentStatus, SessionStatus
from app.schemas.assessment import ClaimReviewRequest, ReviewRequest
from app.services import knowledge_service, report_pdf, session_service, task_service
from app.services.task_service import ACTIVE, TaskProgress

logger = get_logger(__name__)

TASK_KIND = task_service.EVALUATION
BUSY = "An evaluation is already running. Wait for it to finish."
NOT_COMPLETED = "Only a completed interview can be evaluated."
NO_TRANSCRIPT = "This interview has no transcript to evaluate."
NOTHING_TO_EVALUATE = "There are no new completed interviews to evaluate."
NOT_EVALUATED = "This interview has not been evaluated yet."
NO_SUGGESTIONS = (
    "The question bank could not be searched when this interview was evaluated. "
    "Evaluate it again to get suggestions."
)
UNKNOWN_SUGGESTION = "Some of the chosen questions are not among the suggestions."
NOT_A_DRAFT = "This report is not waiting for review."
NO_REPORT = "This interview's report has not been written yet."
HAS_REPORT = "This interview already has a report. Evaluate it again to write a new one."
UNKNOWN_POINT = "Some of the chosen points are not in the report."
CLAIMS_CHECKED = "This interview's CV claims are already checked."
CLAIMS_NOT_CHECKED = (
    "The AI service was not available to check the CV claims. Try again in a moment."
)
UNKNOWN_CLAIM = "This claim is not in the interview's CV claim check."
CLAIM_NOT_TO_CHECK = "Only a contradiction or an unverified claim can be marked."
NO_CLAIM_CHECK = "This interview's CV claims have not been checked yet."
CHECKING_CLAIMS = "checking CV claims"
WRITING_REPORT = "writing the report"
CHECKING_QUALITY = "checking interview quality"
QUALITY_CHECKED = "This interview's quality is already checked."
QUALITY_NOT_WRITTEN = (
    "The AI service was not available to write the recommendations. Try again in a moment."
)
QUALITY_FAILED = "The interview quality could not be checked. Try again in a moment."
REWRITE_FAILED = (
    "The AI service was not available, so the report was not rewritten. "
    "The draft is unchanged; try again in a moment."
)


@dataclass(frozen=True)
class EvaluationGraphs:
    """The two graphs an evaluation runs, one after the other."""

    qa_analysis: CompiledStateGraph
    final_assessment: CompiledStateGraph


def get_evaluation_graphs() -> EvaluationGraphs:
    return EvaluationGraphs(
        get_qa_analysis_graph(), final_graph.get_final_assessment_graph()
    )


class EvaluationFailed(AppError):
    """An interview could not be evaluated. The message is safe to show."""


def ensure_no_evaluation(db: Session) -> None:
    if db.scalar(
        select(Task.id).where(Task.kind == TASK_KIND, Task.status.in_(ACTIVE)).limit(1)
    ):
        raise ConflictError(BUSY)


def _has_turns(session_id):
    return exists().where(TranscriptTurn.session_id == session_id)


def start_evaluation(
    db: Session,
    background_tasks: BackgroundTasks,
    graphs: EvaluationGraphs,
    session_id: int,
    user_id: int,
) -> Task:
    """Evaluate one interview. An interview evaluated before is evaluated
    again, and its earlier assessment is replaced."""
    session = session_service.get_session(db, session_id)
    if session.status != SessionStatus.COMPLETED:
        raise ConflictError(NOT_COMPLETED)
    if not db.scalar(select(_has_turns(session_id))):
        raise ConflictError(NO_TRANSCRIPT)
    ensure_no_evaluation(db)
    return task_service.start_task(
        db,
        background_tasks,
        TASK_KIND,
        user_id,
        lambda progress: run_evaluation(graphs, [session_id], progress),
        job_id=session.job_id,
    )


def sessions_to_evaluate(db: Session, job_id: int) -> list[int]:
    """The job's completed interviews with a transcript and no assessment
    yet, earliest first."""
    return list(
        db.scalars(
            select(InterviewSession.id)
            .where(
                InterviewSession.job_id == job_id,
                InterviewSession.status == SessionStatus.COMPLETED,
                _has_turns(InterviewSession.id),
                ~exists().where(Assessment.session_id == InterviewSession.id),
            )
            .order_by(InterviewSession.ended_at, InterviewSession.id)
        )
    )


def start_job_evaluation(
    db: Session,
    background_tasks: BackgroundTasks,
    graphs: EvaluationGraphs,
    job_id: int,
    user_id: int,
) -> Task:
    """Evaluate every completed interview of the job that has not been
    evaluated yet, one after another. Evaluated interviews are left alone,
    so an assessment the interviewer has worked on is never replaced."""
    if db.get(Job, job_id) is None:
        raise NotFoundError("This job does not exist.")
    ensure_no_evaluation(db)
    session_ids = sessions_to_evaluate(db, job_id)
    if not session_ids:
        raise ConflictError(NOTHING_TO_EVALUATE)
    return task_service.start_task(
        db,
        background_tasks,
        TASK_KIND,
        user_id,
        lambda progress: run_evaluation(graphs, session_ids, progress),
        job_id=job_id,
    )


def thread_id(task_id: str, session_id: int) -> str:
    """Each interview of each run is its own thread."""
    return f"evaluation-{task_id}-{session_id}"


def run_evaluation(
    graphs: EvaluationGraphs, session_ids: list[int], progress: TaskProgress
) -> dict[str, int]:
    """Evaluate the interviews one by one. One interview that fails does not
    stop the others; if every interview fails, the task fails with the
    reason."""
    total = len(session_ids)
    evaluated, failures = 0, []
    for done, session_id in enumerate(session_ids):
        progress.note(
            {"session_ids": session_ids, "current": session_id, "failures": failures}
        )
        result = evaluate_one(graphs, session_id, done, total, progress)
        if result.get("failure"):
            failures.append({"session_id": session_id, "reason": result["failure"]})
        else:
            evaluated += 1
    progress.update(total, total, f"Evaluated {evaluated} of {total} interviews")
    progress.note({"session_ids": session_ids, "current": None, "failures": failures})

    log_event(
        logger, "evaluation_finished", total=total, evaluated=evaluated, failed=len(failures)
    )
    if not evaluated:
        raise EvaluationFailed(failures[-1]["reason"])
    return {
        "total": total,
        "evaluated": evaluated,
        "failed": len(failures),
        "session_ids": session_ids,
        "failures": failures,
    }


def evaluate_one(
    graphs: EvaluationGraphs, session_id: int, done: int, total: int, progress: TaskProgress
) -> dict:
    """Run one interview through both graphs, showing how many answers have
    been judged, then that the report is being written. With one interview
    the bar follows its answers; with several it follows the interviews.
    Returns the failure, if any, under "failure"."""
    graph = graphs.qa_analysis
    config = thread_config(thread_id(progress.task_id, session_id))
    config["max_concurrency"] = get_settings().screening_max_parallel
    prefix = f"Interview {done + 1} of {total}"
    progress.update(done, total, f"{prefix} · finding the questions and answers")

    answers, judged = 0, 0
    # Evaluation is background work: its AI calls leave room for the AI
    # Agent and the interview room.
    with ai_client.background_calls():
        try:
            for update in graph.stream(
                {"session_id": session_id}, config, stream_mode="updates"
            ):
                if update.get("segment_qa") and update["segment_qa"].get("pairs"):
                    answers = answers_to_judge(update["segment_qa"]["pairs"])
                elif update.get("evaluate_answers"):
                    judged += len(update["evaluate_answers"].get("evaluations", []))
                else:
                    continue
                message = f"{prefix} · {judged} of {answers} answers evaluated"
                if total == 1:
                    progress.update(judged, answers, message)
                else:
                    progress.update(done, total, message)
            analysis = graph.get_state(config).values
        finally:
            forget_analysis(graph, config)
        if analysis.get("failure"):
            return analysis

        def show(step: str) -> None:
            if total == 1:
                progress.update(answers, answers, f"{prefix} · {step}")
            else:
                progress.update(done, total, f"{prefix} · {step}")

        show(CHECKING_CLAIMS)
        result = write_report(graphs.final_assessment, session_id, show)
        if not result.get("failure"):
            show(CHECKING_QUALITY)
            check_quality(session_id)
        return result


def start_report(
    db: Session,
    background_tasks: BackgroundTasks,
    graph: CompiledStateGraph,
    session_id: int,
    user_id: int,
) -> Task:
    """Write the report of an interview whose answers are already evaluated
    but that has no report yet, for example one evaluated before reports
    existed. The answers are not evaluated again."""
    session = session_service.get_session(db, session_id)
    assessment = get_assessment(db, session_id)
    if assessment.status != AssessmentStatus.ANALYSED:
        raise ConflictError(HAS_REPORT)
    ensure_no_evaluation(db)
    return task_service.start_task(
        db,
        background_tasks,
        TASK_KIND,
        user_id,
        lambda progress: run_report(graph, session_id, progress),
        job_id=session.job_id,
    )


def run_report(graph: CompiledStateGraph, session_id: int, progress: TaskProgress) -> dict:
    """Write one report, keeping the same task details as an evaluation, so
    the screens show its progress and any failure the same way."""
    progress.note({"session_ids": [session_id], "current": session_id, "failures": []})

    def show(step: str) -> None:
        progress.update(0, 1, f"Interview 1 of 1 · {step}")

    show(CHECKING_CLAIMS)
    with ai_client.background_calls():
        result = write_report(graph, session_id, show)
        if not result.get("failure"):
            show(CHECKING_QUALITY)
            check_quality(session_id)
    failures = []
    if result.get("failure"):
        failures = [{"session_id": session_id, "reason": result["failure"]}]
    progress.note({"session_ids": [session_id], "current": None, "failures": failures})
    log_event(logger, "report_written", session_id=session_id, failed=len(failures))
    if failures:
        raise EvaluationFailed(result["failure"])
    progress.update(1, 1, "Report written")
    return {
        "total": 1,
        "evaluated": 1,
        "failed": 0,
        "session_ids": [session_id],
        "failures": [],
    }


def forget_analysis(graph: CompiledStateGraph, config: dict) -> None:
    """Delete the saved state of a Q&A analysis run once it has ended. The
    analysis is saved in the assessment, and a run stopped by a restart is
    started again from the beginning, so the state, which holds the
    transcript and the answers, is never read again."""
    if graph.checkpointer is not None:
        graph.checkpointer.delete_thread(config["configurable"]["thread_id"])


def write_report(graph: CompiledStateGraph, session_id: int, show=None) -> dict:
    """Run the Final Assessment graph until the report waits for review. An
    earlier report of the interview is started afresh. show, if given, is
    told when the claim check is done and the report is being written."""
    config = thread_config(final_graph.thread_id(session_id))
    if graph.checkpointer is not None:
        graph.checkpointer.delete_thread(config["configurable"]["thread_id"])
    for update in graph.stream({"session_id": session_id}, config, stream_mode="updates"):
        if "save_claims" in update and show is not None:
            show(WRITING_REPORT)
    return graph.get_state(config).values


def start_claim_check(
    db: Session,
    background_tasks: BackgroundTasks,
    graph: CompiledStateGraph,
    session_id: int,
    user_id: int,
) -> Task:
    """Check the CV claims of an interview that has a report but no usable
    claim check: evaluated before F8, or the AI was down. Only the claim
    nodes run; the report, its approval and the decision are not touched."""
    session = session_service.get_session(db, session_id)
    assessment = get_assessment(db, session_id)
    if assessment.status == AssessmentStatus.ANALYSED:
        raise ConflictError(NO_REPORT)
    if (assessment.claim_checks or {}).get("status") == cv_claims.CHECKED:
        raise ConflictError(CLAIMS_CHECKED)
    ensure_no_evaluation(db)
    return task_service.start_task(
        db,
        background_tasks,
        TASK_KIND,
        user_id,
        lambda progress: run_claim_check(graph, session_id, progress),
        job_id=session.job_id,
    )


def run_claim_check(graph: CompiledStateGraph, session_id: int, progress: TaskProgress) -> dict:
    """Check one interview's CV claims, keeping the same task details as an
    evaluation (marked claims_only), so the screens show its progress."""
    note = {"session_ids": [session_id], "current": session_id, "claims_only": True}
    progress.note({**note, "failures": []})
    progress.update(0, 1, f"Interview 1 of 1 · {CHECKING_CLAIMS}")
    config = thread_config(final_graph.claims_thread_id(session_id))
    if graph.checkpointer is not None:
        graph.checkpointer.delete_thread(config["configurable"]["thread_id"])
    with ai_client.background_calls():
        graph.invoke({"session_id": session_id, "claims_only": True}, config)
    values = graph.get_state(config).values
    reason = values.get("failure") or (CLAIMS_NOT_CHECKED if values.get("claims_failed") else None)
    failures = [{"session_id": session_id, "reason": reason}] if reason else []
    progress.note({**note, "current": None, "failures": failures})
    if reason:
        raise EvaluationFailed(reason)
    progress.update(1, 1, "CV claims checked")
    return {
        "total": 1,
        "evaluated": 1,
        "failed": 0,
        "session_ids": [session_id],
        "failures": [],
        "claims_only": True,
    }


def check_quality(session_id: int) -> dict:
    """Run the Interview Quality graph (F10) for one interview, on a fresh
    thread. A failure is logged and returned, never raised, so it cannot
    stop an evaluation: the report is written either way."""
    graph = quality_graph.get_interview_quality_graph()
    config = thread_config(quality_graph.thread_id(session_id))
    try:
        if graph.checkpointer is not None:
            graph.checkpointer.delete_thread(config["configurable"]["thread_id"])
        graph.invoke({"session_id": session_id}, config)
        return graph.get_state(config).values
    except Exception as exc:
        log_event(
            logger,
            "interview_quality_error",
            session_id=session_id,
            error_type=type(exc).__name__,
        )
        return {"failure": QUALITY_FAILED}


def start_quality_check(
    db: Session, background_tasks: BackgroundTasks, session_id: int, user_id: int
) -> Task:
    """Check how an interview was run, for one evaluated before F10 or whose
    recommendations could not be written. Only the Interview Quality graph
    runs; the report, its approval and the decision are not touched."""
    session = session_service.get_session(db, session_id)
    assessment = get_assessment(db, session_id)
    if assessment.status == AssessmentStatus.ANALYSED:
        raise ConflictError(NO_REPORT)
    quality = assessment.interview_quality or {}
    written = (quality.get("recommendations") or {}).get("status")
    if quality and written != quality_graph.NOT_WRITTEN:
        raise ConflictError(QUALITY_CHECKED)
    ensure_no_evaluation(db)
    return task_service.start_task(
        db,
        background_tasks,
        TASK_KIND,
        user_id,
        lambda progress: run_quality_check(session_id, progress),
        job_id=session.job_id,
    )


def run_quality_check(session_id: int, progress: TaskProgress) -> dict:
    """Check one interview's quality, keeping the same task details as an
    evaluation (marked quality_only), so the screens show its progress."""
    note = {"session_ids": [session_id], "current": session_id, "quality_only": True}
    progress.note({**note, "failures": []})
    progress.update(0, 1, f"Interview 1 of 1 · {CHECKING_QUALITY}")
    with ai_client.background_calls():
        values = check_quality(session_id)
    reason = values.get("failure") or (QUALITY_NOT_WRITTEN if values.get("ai_failed") else None)
    failures = [{"session_id": session_id, "reason": reason}] if reason else []
    progress.note({**note, "current": None, "failures": failures})
    if reason:
        raise EvaluationFailed(reason)
    progress.update(1, 1, "Interview quality checked")
    return {
        "total": 1,
        "evaluated": 1,
        "failed": 0,
        "session_ids": [session_id],
        "failures": [],
        "quality_only": True,
    }


def _consistency_row(session: InterviewSession) -> dict:
    quality = session.assessment.interview_quality
    metrics = quality["metrics"]
    return {
        "session_id": session.id,
        "candidate_name": session.candidate.full_name if session.candidate else "",
        "interview_at": session.started_at or session.scheduled_start,
        "minutes": metrics.get("actual_minutes"),
        "questions": metrics.get("job_questions", 0),
        "candidate_share": metrics.get("candidate_share"),
        "explored": quality.get("explored", []),
        "requirements": quality.get("requirements", []),
        "quality_score": quality.get("score"),
        "quality_label": quality.get("label"),
    }


def interview_consistency(db: Session, job_id: int) -> dict:
    """How similar the job's checked interviews were (F10): the typical
    interview, how many asked each requirement and how each one differs."""
    if db.get(Job, job_id) is None:
        raise NotFoundError("This job does not exist.")
    sessions = db.scalars(
        select(InterviewSession)
        .where(
            InterviewSession.job_id == job_id,
            InterviewSession.status == SessionStatus.COMPLETED,
        )
        .options(
            selectinload(InterviewSession.candidate),
            selectinload(InterviewSession.assessment),
        )
        .order_by(InterviewSession.ended_at, InterviewSession.id)
    ).all()
    rows = [
        _consistency_row(session)
        for session in sessions
        if session.assessment is not None
        and (session.assessment.interview_quality or {}).get("status") == quality_graph.CHECKED
    ]
    return consistency.job_consistency(rows)


def review_claim(
    db: Session, session_id: int, claim_id: str, review: ClaimReviewRequest, user_id: int
) -> Assessment:
    """Mark a contradiction or an unverified claim as checked or dismissed,
    with an optional note, or open it again. Records who did it and when.
    Nothing else changes: no score, the report or the decision."""
    assessment = get_assessment(db, session_id)
    checks = assessment.claim_checks
    if not checks or checks.get("status") != cv_claims.CHECKED:
        raise ConflictError(NO_CLAIM_CHECK)
    claim = next((item for item in checks["claims"] if item["id"] == claim_id), None)
    if claim is None:
        raise NotFoundError(UNKNOWN_CLAIM)
    if claim["result"] not in cv_claims.TO_CHECK:
        raise ConflictError(CLAIM_NOT_TO_CHECK)

    marked = None
    if review.action != "reopen":
        user = db.get(User, user_id)
        marked = {
            "status": review.action,
            "note": (review.note or "").strip() or None,
            "by_id": user_id,
            "by_name": user.full_name if user else None,
            "at": datetime.now(timezone.utc).isoformat(),
        }
    # A new dict, so the change to the JSON column is saved.
    assessment.claim_checks = {
        **checks,
        "claims": [
            {**item, "review": marked} if item["id"] == claim_id else item
            for item in checks["claims"]
        ],
    }
    db.commit()
    log_event(
        logger,
        "cv_claim_reviewed",
        session_id=session_id,
        claim_id=claim_id,
        action=review.action,
        has_note=bool(marked and marked["note"]),
    )
    db.refresh(assessment)
    return assessment


def evaluation_activity(db: Session, job_id: int) -> dict:
    """The job's evaluation that is running, its last finished one and how
    many completed interviews have not been evaluated yet."""
    if db.get(Job, job_id) is None:
        raise NotFoundError("This job does not exist.")
    running = db.scalar(
        select(Task)
        .where(Task.job_id == job_id, Task.kind == TASK_KIND, Task.status.in_(ACTIVE))
        .limit(1)
    )
    return {
        "running": running,
        "last": task_service.last_finished(db, job_id, TASK_KIND),
        "waiting": len(sessions_to_evaluate(db, job_id)),
    }


def _coverage_counts(coverage: list[dict] | None) -> dict | None:
    if coverage is None:
        return None
    statuses = [entry["status"] for entry in coverage]
    return {
        "covered": statuses.count(coverage_rules.COVERED),
        "weak": statuses.count(coverage_rules.WEAK),
        "not_explored": statuses.count(coverage_rules.NOT_EXPLORED),
        "total": len(statuses),
    }


def _ranked_row(session: InterviewSession) -> dict:
    assessment = session.assessment
    candidate = session.candidate
    # Scores and points exist once the report is written (draft or approved).
    has_report = assessment is not None and assessment.status != AssessmentStatus.ANALYSED
    report = assessment if has_report else None
    screening = candidate.scores["final_score"] if candidate and candidate.scores else None
    return {
        "session_id": session.id,
        "candidate_id": session.candidate_id,
        "candidate_name": candidate.full_name if candidate else "",
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "scheduled_start": session.scheduled_start,
        "rank": None,
        "status": assessment.status if assessment else None,
        "cv_score": report.cv_score if report else screening,
        "interview_score": report.interview_score if report else None,
        "interview_dimensions": report.interview_dimensions if report else None,
        "overall_score": report.overall_score if report else None,
        "suitability": report.suitability if report else None,
        "answers_evaluated": len(scoring.evaluated(assessment.qa_evaluations))
        if assessment
        else 0,
        "coverage": _coverage_counts(assessment.coverage_map if assessment else None),
        "coverage_map": assessment.coverage_map if assessment else None,
        "strengths": report.strengths if report else None,
        "weaknesses": report.weaknesses if report else None,
        "gaps": report.gaps if report else None,
        "areas_to_verify": report.areas_to_verify if report else None,
        "approved_at": report.approved_at if report else None,
        "open_contradictions": cv_claims.open_contradictions(
            assessment.claim_checks if assessment else None
        ),
        "decision": getattr(candidate, "decision", None),
        "feedback_status": getattr(candidate, "feedback_status", None),
        "feedback_warnings": getattr(candidate, "feedback_warnings", 0),
    }


def ranked_assessments(db: Session, job_id: int) -> list[dict]:
    """The job's completed interviews, ranked by overall score (draft and
    approved reports alike). A tie goes to the higher interview score, then
    by name. Interviews without an overall score follow, unranked, latest
    first."""
    if db.get(Job, job_id) is None:
        raise NotFoundError("This job does not exist.")
    sessions = db.scalars(
        select(InterviewSession)
        .where(
            InterviewSession.job_id == job_id,
            InterviewSession.status == SessionStatus.COMPLETED,
        )
        .options(
            selectinload(InterviewSession.candidate).selectinload(Candidate.feedback),
            selectinload(InterviewSession.assessment),
        )
    ).all()
    rows = [_ranked_row(session) for session in sessions]
    ranked = sorted(
        (row for row in rows if row["overall_score"] is not None),
        key=lambda row: (
            -row["overall_score"],
            -(row["interview_score"] or 0),
            row["candidate_name"].lower(),
        ),
    )
    for rank, row in enumerate(ranked, start=1):
        row["rank"] = rank
    unranked = sorted(
        (row for row in rows if row["overall_score"] is None),
        key=lambda row: row["started_at"] or row["scheduled_start"],
        reverse=True,
    )
    return ranked + unranked


def get_assessment(db: Session, session_id: int) -> Assessment:
    session_service.get_session(db, session_id)
    assessment = db.scalar(select(Assessment).where(Assessment.session_id == session_id))
    if assessment is None:
        raise NotFoundError(NOT_EVALUATED)
    return assessment


def add_suggested_questions(
    db: Session, session_id: int, pair_ids: list[str], user_id: int
) -> list[dict]:
    """Add the suggested questions the interviewer ticked to the question
    bank, and mark them as added. A question added before is not added
    again. Returns the updated suggestions."""
    assessment = get_assessment(db, session_id)
    if assessment.question_suggestions is None:
        raise ConflictError(NO_SUGGESTIONS)
    by_pair = {item["pair_id"]: item for item in assessment.question_suggestions}
    if any(pair_id not in by_pair for pair_id in pair_ids):
        raise AppError(UNKNOWN_SUGGESTION)

    chosen = [by_pair[pair_id] for pair_id in dict.fromkeys(pair_ids)]
    new = [item for item in chosen if not item["added"]]
    if new:
        session = session_service.get_session(db, session_id)
        job = db.get(Job, session.job_id)
        knowledge_service.add_interview_questions(
            db, job.job_code, job.title, [item["question"] for item in new], user_id
        )
        added = {item["pair_id"] for item in new}
        # A new list, so the change to the JSON column is saved.
        assessment.question_suggestions = [
            {**item, "added": item["added"] or item["pair_id"] in added}
            for item in assessment.question_suggestions
        ]
        db.commit()
    log_event(logger, "suggested_questions_added", session_id=session_id, count=len(new))
    return assessment.question_suggestions


def review_assessment(
    db: Session,
    graph: CompiledStateGraph,
    session_id: int,
    review: ReviewRequest,
    user_id: int,
) -> Assessment:
    """Continue the paused report with the interviewer's review: approve it,
    ask the AI to rewrite it following a note, or edit it (a new summary,
    points removed). Returns the assessment as it is afterwards."""
    assessment = get_assessment(db, session_id)
    config = thread_config(final_graph.thread_id(session_id))
    waiting = final_graph.is_waiting_for_review(graph, config)
    if assessment.status != AssessmentStatus.DRAFT or not waiting:
        raise ConflictError(NOT_A_DRAFT)
    claims = (assessment.strengths or []) + (assessment.weaknesses or [])
    points = {claim["id"] for claim in claims}
    if any(point not in points for point in review.remove):
        raise AppError(UNKNOWN_POINT)

    graph.invoke(
        Command(resume={**review.model_dump(), "user_id": user_id}),
        config,
    )
    if graph.get_state(config).values.get("revision_failed"):
        raise ServiceUnavailableError(REWRITE_FAILED)
    log_event(logger, "assessment_reviewed", session_id=session_id, action=review.action)
    db.refresh(assessment)
    return assessment


def approve_all_drafts(
    db: Session, graph: CompiledStateGraph, job_id: int, user_id: int
) -> dict[str, int]:
    """Approve every draft report of the job that is waiting for review, as
    if each were approved one by one. A draft being written again is left
    alone and counted as skipped."""
    if db.get(Job, job_id) is None:
        raise NotFoundError("This job does not exist.")
    session_ids = db.scalars(
        select(Assessment.session_id)
        .join(InterviewSession, InterviewSession.id == Assessment.session_id)
        .where(InterviewSession.job_id == job_id, Assessment.status == AssessmentStatus.DRAFT)
    ).all()
    approved = 0
    for session_id in session_ids:
        config = thread_config(final_graph.thread_id(session_id))
        if not final_graph.is_waiting_for_review(graph, config):
            continue
        graph.invoke(Command(resume={"action": "approve", "user_id": user_id}), config)
        approved += 1
    log_event(
        logger,
        "assessments_approved",
        job_id=job_id,
        approved=approved,
        skipped=len(session_ids) - approved,
    )
    return {"approved": approved, "skipped": len(session_ids) - approved}


def report_file(db: Session, session_id: int, time_zone: str | None) -> tuple[bytes, str]:
    """The interview's report as a PDF, with its file name. Dates and times
    are shown in time_zone (the interviewer's), or UTC."""
    assessment = get_assessment(db, session_id)
    if assessment.status == AssessmentStatus.ANALYSED:
        raise ConflictError(NO_REPORT)
    session = session_service.get_session(db, session_id)
    job = db.get(Job, session.job_id)
    context = report_pdf.report_context(assessment, session, job, time_zone)
    content = report_pdf.build_pdf(context)
    log_event(logger, "report_pdf_built", session_id=session_id, size=len(content))
    start = session.started_at or session.scheduled_start
    return content, report_pdf.file_name(job.job_code, start)
