"""Post-interview assessment endpoints: evaluating interviews and reading
the result. Interviewers only."""

from fastapi import APIRouter, BackgroundTasks, Depends, status
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_interviewer
from app.db.session import get_db
from app.graphs.final_assessment.graph import get_final_assessment_graph
from app.models import Assessment, Task
from app.schemas.assessment import (
    AddQuestionsRequest,
    ApproveAllResult,
    AssessmentOut,
    EvaluationActivity,
    QuestionSuggestion,
    RankedAssessment,
    ReviewRequest,
)
from app.schemas.error import ErrorResponse
from app.schemas.task import TaskResponse
from app.services import evaluation_service
from app.services.evaluation_service import EvaluationGraphs, get_evaluation_graphs

job_router = APIRouter(
    prefix="/jobs/{job_id}", tags=["Assessments"], dependencies=[Depends(require_interviewer)]
)
session_router = APIRouter(
    prefix="/interviews", tags=["Assessments"], dependencies=[Depends(require_interviewer)]
)


@session_router.post(
    "/{session_id}/evaluate",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Evaluate one completed interview",
    responses={
        404: {"model": ErrorResponse, "description": "Interview not found"},
        409: {
            "model": ErrorResponse,
            "description": "Not completed, no transcript, or an evaluation is running",
        },
    },
)
def evaluate_interview(
    session_id: int,
    background_tasks: BackgroundTasks,
    principal: Principal = Depends(require_interviewer),
    db: Session = Depends(get_db),
    graphs: EvaluationGraphs = Depends(get_evaluation_graphs),
) -> Task:
    """Starts in the background and returns a task; follow it with
    GET /tasks/{id}. The answers are evaluated, then the report is written
    and waits for review as a draft. An interview evaluated before is
    evaluated again and its earlier assessment is replaced."""
    return evaluation_service.start_evaluation(
        db, background_tasks, graphs, session_id, principal.subject_id
    )


@session_router.post(
    "/{session_id}/report",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Write the report of an interview whose answers are evaluated",
    responses={
        404: {"model": ErrorResponse, "description": "Interview not found or not evaluated"},
        409: {
            "model": ErrorResponse,
            "description": "It already has a report, or an evaluation is running",
        },
    },
)
def write_interview_report(
    session_id: int,
    background_tasks: BackgroundTasks,
    principal: Principal = Depends(require_interviewer),
    db: Session = Depends(get_db),
    graph: CompiledStateGraph = Depends(get_final_assessment_graph),
) -> Task:
    """Starts in the background and returns a task, like an evaluation. Only
    the report is written, from the answers already evaluated, and it waits
    for review as a draft. For an interview evaluated before reports
    existed."""
    return evaluation_service.start_report(
        db, background_tasks, graph, session_id, principal.subject_id
    )


@job_router.post(
    "/evaluate",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Evaluate the job's completed interviews not evaluated yet",
    responses={
        404: {"model": ErrorResponse, "description": "Job not found"},
        409: {
            "model": ErrorResponse,
            "description": "Nothing new to evaluate, or an evaluation is running",
        },
    },
)
def evaluate_job_interviews(
    job_id: int,
    background_tasks: BackgroundTasks,
    principal: Principal = Depends(require_interviewer),
    db: Session = Depends(get_db),
    graphs: EvaluationGraphs = Depends(get_evaluation_graphs),
) -> Task:
    """Evaluates the interviews one after another in one background task.
    Interviews that already have an assessment are skipped."""
    return evaluation_service.start_job_evaluation(
        db, background_tasks, graphs, job_id, principal.subject_id
    )


@job_router.get(
    "/evaluation",
    response_model=EvaluationActivity,
    summary="See the job's interview evaluations",
    responses={404: {"model": ErrorResponse, "description": "Job not found"}},
)
def read_evaluation(job_id: int, db: Session = Depends(get_db)) -> dict:
    """The evaluation running now, with the interviews it covers and the one
    it is on, the last finished one with any interviews that failed, and how
    many completed interviews have not been evaluated yet. The screens ask
    every few seconds while one runs."""
    return evaluation_service.evaluation_activity(db, job_id)


@job_router.get(
    "/assessments",
    response_model=list[RankedAssessment],
    summary="List the job's assessed candidates, ranked",
    responses={404: {"model": ErrorResponse, "description": "Job not found"}},
)
def list_ranked_assessments(job_id: int, db: Session = Depends(get_db)) -> list[dict]:
    """Every completed interview of the job. Those with an overall score come
    first, ranked by it (draft and approved reports alike; a tie goes to the
    higher interview score, then by name), each with its scores, label,
    requirement coverage counts and the report's points with their sources.
    The rest follow unranked: not evaluated yet, only analysed, or without
    an overall score."""
    return evaluation_service.ranked_assessments(db, job_id)


@job_router.post(
    "/assessments/approve",
    response_model=ApproveAllResult,
    summary="Approve all the job's draft reports",
    responses={404: {"model": ErrorResponse, "description": "Job not found"}},
)
def approve_all_reports(
    job_id: int,
    principal: Principal = Depends(require_interviewer),
    db: Session = Depends(get_db),
    graph: CompiledStateGraph = Depends(get_final_assessment_graph),
) -> dict:
    """Approves every draft report waiting for review, the same as approving
    each one: it becomes final and its candidate is marked assessed. A draft
    being rewritten at that moment is skipped."""
    return evaluation_service.approve_all_drafts(db, graph, job_id, principal.subject_id)


@session_router.get(
    "/{session_id}/assessment",
    response_model=AssessmentOut,
    summary="Read the interview's assessment",
    responses={404: {"model": ErrorResponse, "description": "Not found or not evaluated"}},
)
def read_assessment(session_id: int, db: Session = Depends(get_db)) -> Assessment:
    """The question-answer pairs found in the transcript, each pointing to its
    transcript turns, with each answer's evaluation: four criteria with
    reasons, a score worked out by rule, a justification and a quote from the
    answer. Small talk is kept but marked, and is not evaluated. Also the
    coverage of each job requirement, next to its CV screening result, and
    the new questions offered for the question bank. Once the report is
    written: the CV, interview and overall scores with the suitability label,
    the summary, and the strengths, weaknesses, evidence gaps and areas to
    verify, each pointing to a transcript segment or a CV result."""
    return evaluation_service.get_assessment(db, session_id)


@session_router.post(
    "/{session_id}/assessment/questions",
    response_model=list[QuestionSuggestion],
    summary="Add ticked questions to the question bank",
    responses={
        400: {"model": ErrorResponse, "description": "A question is not a suggestion"},
        404: {"model": ErrorResponse, "description": "Not found or not evaluated"},
        409: {"model": ErrorResponse, "description": "No suggestions were made"},
        503: {"model": ErrorResponse, "description": "The embedding model is unavailable"},
    },
)
def add_questions(
    session_id: int,
    payload: AddQuestionsRequest,
    principal: Principal = Depends(require_interviewer),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Adds the chosen suggestions to the question bank, in one Knowledge Base
    document per job ("Interview questions - <job code>.txt") with the job
    title as its role. Questions added before are not added again. Returns
    the suggestions, each marked when added."""
    return evaluation_service.add_suggested_questions(
        db, session_id, payload.pair_ids, principal.subject_id
    )


@session_router.post(
    "/{session_id}/assessment/review",
    response_model=AssessmentOut,
    summary="Approve, edit or ask for changes to the draft report",
    responses={
        400: {"model": ErrorResponse, "description": "A point to remove is not in the report"},
        404: {"model": ErrorResponse, "description": "Not found or not evaluated"},
        409: {"model": ErrorResponse, "description": "The report is not waiting for review"},
        503: {"model": ErrorResponse, "description": "The AI could not rewrite the report"},
    },
)
def review_report(
    session_id: int,
    payload: ReviewRequest,
    principal: Principal = Depends(require_interviewer),
    db: Session = Depends(get_db),
    graph: CompiledStateGraph = Depends(get_final_assessment_graph),
) -> Assessment:
    """approve: the report is final and the candidate becomes assessed.
    request_changes: the AI rewrites the report following the note, checks
    every point again, and the new draft waits for review. edit: a new
    summary and/or strengths and weaknesses removed (none can be added),
    and the draft waits for review again."""
    return evaluation_service.review_assessment(
        db, graph, session_id, payload, principal.subject_id
    )
