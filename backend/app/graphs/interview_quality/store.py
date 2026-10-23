"""Database reads and writes for the Interview Quality graph.

Kept apart from the graph so its nodes stay easy to follow and to test.
The transcript's text never leaves this file: each turn is passed on with
its speaker, times and word count only.
"""

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Assessment, InterviewSession, Job, TranscriptTurn


def _ms(start, end) -> int | None:
    if start is None or end is None:
        return None
    return max(int((end - start).total_seconds() * 1000), 0)


def load_interview(session_id: int) -> dict | None:
    """The interview's Q&A analysis, its turns (speaker, times and word
    count), its planned and actual length and the job title, or None when
    the interview has not been analysed."""
    with SessionLocal() as db:
        assessment = db.scalar(select(Assessment).where(Assessment.session_id == session_id))
        session = db.get(InterviewSession, session_id)
        if assessment is None or session is None:
            return None
        job = db.get(Job, session.job_id)
        turns = db.scalars(
            select(TranscriptTurn)
            .where(TranscriptTurn.session_id == session_id)
            .order_by(TranscriptTurn.start_ms, TranscriptTurn.id)
        )
        return {
            "job_title": job.title if job else "",
            "pairs": assessment.qa_evaluations or [],
            "coverage": assessment.coverage_map or [],
            "planned_ms": _ms(session.scheduled_start, session.scheduled_end),
            "actual_ms": _ms(session.started_at, session.ended_at),
            "turns": [
                {
                    "id": turn.id,
                    "speaker": turn.speaker,
                    "start_ms": turn.start_ms,
                    "end_ms": turn.end_ms,
                    "words": len((turn.text or "").split()),
                }
                for turn in turns
            ],
        }


def save_quality(session_id: int, quality: dict) -> None:
    """Keep the interview quality check with the assessment. Nothing else of
    the assessment is touched."""
    with SessionLocal() as db:
        assessment = db.scalar(select(Assessment).where(Assessment.session_id == session_id))
        if assessment is not None:
            assessment.interview_quality = quality
            db.commit()
