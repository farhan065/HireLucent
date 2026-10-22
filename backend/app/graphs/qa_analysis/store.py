"""Database reads and writes for the Q&A Analysis graph.

Kept apart from the graph so its nodes stay easy to follow and to test.
"""

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Assessment, Candidate, InterviewSession, Job, TranscriptTurn
from app.models.enums import AssessmentStatus

# Filled in by later steps of the evaluation. Cleared when an interview is
# evaluated again, so an old report never sits next to a new analysis.
LATER_FIELDS = (
    "cv_score",
    "interview_score",
    "overall_score",
    "strengths",
    "weaknesses",
    "gaps",
    "areas_to_verify",
    "report",
    "claim_checks",
    "approved_by",
    "approved_at",
)


def load_interview(session_id: int) -> dict | None:
    """The interview, its job title and requirements, the candidate's CV
    screening result per requirement, and the turns in the order spoken, or
    None when the interview no longer exists."""
    with SessionLocal() as db:
        session = db.get(InterviewSession, session_id)
        if session is None:
            return None
        job = db.get(Job, session.job_id)
        candidate = db.get(Candidate, session.candidate_id)
        turns = db.scalars(
            select(TranscriptTurn)
            .where(TranscriptTurn.session_id == session_id)
            .order_by(TranscriptTurn.start_ms, TranscriptTurn.id)
        )
        return {
            "candidate_id": session.candidate_id,
            "status": session.status,
            "job_title": job.title if job else "",
            "requirements": (job.requirements or {}).get("items", []) if job else [],
            "cv_matches": candidate.requirement_matches if candidate else None,
            "turns": [
                {
                    "id": turn.id,
                    "speaker": turn.speaker,
                    "start_ms": turn.start_ms,
                    "end_ms": turn.end_ms,
                    "text": turn.text,
                }
                for turn in turns
            ],
        }


def save_analysis(
    session_id: int,
    candidate_id: int,
    pairs: list[dict],
    coverage: list[dict],
    suggestions: list[dict] | None,
) -> None:
    """Keep the evaluated pairs, the requirement coverage and the question
    bank suggestions. Evaluating an interview again replaces its earlier
    analysis, because each interview has one assessment."""
    with SessionLocal() as db:
        assessment = db.scalar(select(Assessment).where(Assessment.session_id == session_id))
        if assessment is None:
            assessment = Assessment(session_id=session_id, candidate_id=candidate_id)
            db.add(assessment)
        else:
            for field in LATER_FIELDS:
                setattr(assessment, field, None)
        assessment.status = AssessmentStatus.ANALYSED
        assessment.qa_evaluations = pairs
        assessment.coverage_map = coverage
        assessment.question_suggestions = suggestions
        db.commit()
