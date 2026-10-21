"""Decisions and feedback emails (innovation feature F11, Candidate Feedback
Composer). Interviewers only; candidates get 403."""

from fastapi import APIRouter, BackgroundTasks, Depends, status
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_interviewer
from app.db.session import get_db
from app.models import Candidate, CandidateFeedback, Task
from app.schemas.error import ErrorResponse
from app.schemas.feedback import (
    CandidateDecision,
    ComposeRequest,
    DecisionChange,
    DecisionResult,
    DecisionRule,
    FeedbackActivity,
    FeedbackOut,
    FeedbackReview,
    SendAllRequest,
)
from app.schemas.task import TaskResponse
from app.services import feedback_service
from app.services.feedback_service import get_feedback_graph

job_router = APIRouter(
    prefix="/jobs/{job_id}", tags=["Feedback"], dependencies=[Depends(require_interviewer)]
)
candidate_router = APIRouter(
    prefix="/candidates", tags=["Feedback"], dependencies=[Depends(require_interviewer)]
)

JOB_NOT_FOUND = {404: {"model": ErrorResponse, "description": "Job not found"}}
CANDIDATE_NOT_FOUND = {404: {"model": ErrorResponse, "description": "Candidate not found"}}


@candidate_router.put(
    "/{candidate_id}/decision",
    response_model=CandidateDecision,
    summary="Hire or reject a candidate after the interview",
    responses={
        **CANDIDATE_NOT_FOUND,
        409: {"model": ErrorResponse, "description": "Report not approved, or email sent"},
    },
)
def change_decision(
    candidate_id: int,
    payload: DecisionChange,
    principal: Principal = Depends(require_interviewer),
    db: Session = Depends(get_db),
) -> Candidate:
    """Only after the candidate's report is approved. The decision can change
    (or be taken back with null) until the feedback email is sent; an email
    written for the old decision and not sent is removed."""
    return feedback_service.set_decision(
        db, candidate_id, payload.decision, principal.subject_id
    )


@job_router.post(
    "/decisions",
    response_model=DecisionResult,
    summary="Hire the top candidates by a rule and reject the rest",
    responses=JOB_NOT_FOUND,
)
def apply_decision_rule(
    job_id: int,
    payload: DecisionRule,
    principal: Principal = Depends(require_interviewer),
    db: Session = Depends(get_db),
) -> dict:
    """Hire the top N ranked candidates, or everyone with at least an overall
    score; the other ranked candidates are rejected. Only approved reports
    count. Candidates whose email is sent keep their decision."""
    return feedback_service.decide_by_rule(db, job_id, payload, principal.subject_id)


@job_router.get(
    "/feedback",
    response_model=FeedbackActivity,
    summary="See the job's feedback emails",
    responses=JOB_NOT_FOUND,
)
def read_feedback_activity(job_id: int, db: Session = Depends(get_db)) -> dict:
    """The writing or sending running now, the last finished one with any
    candidates that failed, and how many emails are still to send after
    screening and after the interview. The screens ask every few seconds
    while one runs."""
    return feedback_service.activity(db, job_id)


@job_router.post(
    "/feedback",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Write the feedback emails of chosen candidates",
    responses={
        **JOB_NOT_FOUND,
        409: {"model": ErrorResponse, "description": "Nothing to write, or a run is going"},
    },
)
def write_emails(
    job_id: int,
    payload: ComposeRequest,
    background_tasks: BackgroundTasks,
    principal: Principal = Depends(require_interviewer),
    db: Session = Depends(get_db),
    graph: CompiledStateGraph = Depends(get_feedback_graph),
) -> Task:
    """Starts in the background and returns a task. Each email is written by
    LangGraph 5 from the candidate's own results (the AI for rejections, a
    fixed message for a hire or a CV that could not be read), checked for
    fairness, and saved as a draft. Nothing is sent."""
    return feedback_service.start_writing(
        db, background_tasks, graph, job_id, payload.candidate_ids, principal.subject_id
    )


@job_router.post(
    "/feedback/send",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send every draft of a stage that passed the fairness check",
    responses={
        **JOB_NOT_FOUND,
        409: {"model": ErrorResponse, "description": "Nothing ready, or a run is going"},
    },
)
def send_all(
    job_id: int,
    payload: SendAllRequest,
    background_tasks: BackgroundTasks,
    principal: Principal = Depends(require_interviewer),
    db: Session = Depends(get_db),
    graph: CompiledStateGraph = Depends(get_feedback_graph),
) -> Task:
    """The same as approving each passed draft one by one. Drafts with
    fairness warnings are left for one-by-one review."""
    return feedback_service.start_sending(
        db, background_tasks, graph, job_id, payload.stage, principal.subject_id
    )


@candidate_router.get(
    "/{candidate_id}/feedback",
    response_model=FeedbackOut,
    summary="Read a candidate's feedback email",
    responses={404: {"model": ErrorResponse, "description": "Candidate or email not found"}},
)
def read_feedback(candidate_id: int, db: Session = Depends(get_db)) -> CandidateFeedback:
    """The draft or the email as sent, with what each point is based on
    (for the interviewer only) and any fairness warnings."""
    return feedback_service.get_feedback(db, candidate_id)


@candidate_router.post(
    "/{candidate_id}/feedback/review",
    response_model=FeedbackOut,
    summary="Approve and send, edit, rewrite or discard a draft email",
    responses={
        404: {"model": ErrorResponse, "description": "Candidate or email not found"},
        409: {"model": ErrorResponse, "description": "Not waiting for review, or has warnings"},
        503: {"model": ErrorResponse, "description": "The AI could not rewrite the email"},
    },
)
def review_feedback(
    candidate_id: int,
    payload: FeedbackReview,
    principal: Principal = Depends(require_interviewer),
    db: Session = Depends(get_db),
    graph: CompiledStateGraph = Depends(get_feedback_graph),
) -> CandidateFeedback:
    """approve: send it (refused while it has warnings). send_anyway: send it
    with its warnings, which are kept with the email. edit: save your text,
    which is checked again. request_changes: the AI rewrites it following
    the note (AI emails only). discard: nothing is sent. A draft that could
    not be sent (status failed) is approved again to try again."""
    return feedback_service.review(db, graph, candidate_id, payload, principal.subject_id)
