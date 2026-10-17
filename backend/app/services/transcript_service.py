"""The interview transcript: saving turns as they come, reading them back,
and the job keywords that help speech-to-text recognise technical words.

Turns are saved one by one while the interview runs, so a restart of the
worker or the browser loses nothing that was already said.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InterviewSession, Job, TranscriptTurn
from app.services import session_service

# How many keywords are sent. The service allows a limited list, and a short
# list of specific terms works best.
MAX_KEYTERMS = 50
MAX_KEYTERM_LENGTH = 40
# Everyday words that would only bias ordinary speech, so they are not sent.
COMMON_WORDS = {
    "analysis",
    "communication",
    "data",
    "degree",
    "design",
    "development",
    "engineering",
    "experience",
    "leadership",
    "management",
    "problem solving",
    "project",
    "skills",
    "software",
    "team",
    "teamwork",
    "testing",
    "work",
}


def add_turn(
    db: Session, session_id: int, speaker: str, start_ms: int, end_ms: int, text: str
) -> TranscriptTurn:
    turn = TranscriptTurn(
        session_id=session_id, speaker=speaker, start_ms=start_ms, end_ms=end_ms, text=text
    )
    db.add(turn)
    db.commit()
    return turn


def read_transcript(db: Session, session_id: int) -> dict:
    """The interview's turns in the order they were spoken, each with its
    time from the start and the clock time."""
    session = session_service.get_session(db, session_id)
    turns = db.scalars(
        select(TranscriptTurn)
        .where(TranscriptTurn.session_id == session_id)
        .order_by(TranscriptTurn.start_ms, TranscriptTurn.id)
    )
    return {
        "session_id": session.id,
        "started_at": session.started_at,
        "turns": [
            {
                "id": turn.id,
                "speaker": turn.speaker,
                "start_ms": turn.start_ms,
                "end_ms": turn.end_ms,
                "spoken_at": session.started_at + timedelta(milliseconds=turn.start_ms)
                if session.started_at
                else None,
                "text": turn.text,
            }
            for turn in turns
        ],
    }


def keyterms(requirements: dict) -> list[str]:
    """The job's requirement keywords worth sending: must-haves first,
    without repeats or everyday words."""
    items = sorted(
        requirements.get("items", []), key=lambda item: item.get("priority") != "must_have"
    )
    terms: list[str] = []
    for item in items:
        for keyword in item.get("keywords", []):
            term = keyword.strip()
            if (
                term
                and term.lower() not in COMMON_WORDS
                and len(term) <= MAX_KEYTERM_LENGTH
                and term not in terms
            ):
                terms.append(term)
    return terms[:MAX_KEYTERMS]


def keyterms_for_session(db: Session, session_id: int) -> list[str]:
    """The keywords of the job this interview is for. Job keywords only:
    nothing about the candidate is sent."""
    session = db.get(InterviewSession, session_id)
    job = db.get(Job, session.job_id) if session else None
    return keyterms(job.requirements or {}) if job else []
