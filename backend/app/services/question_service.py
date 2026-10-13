"""QuestionService: interview questions suggested for one candidate.

The interviewer asks for them in the interview room, five at a time. The AI
writes them from the candidate's CV and screening results only, starting
with the requirements the CV covers least. Each question is saved with the
interview, together with whether the interviewer has asked it.
"""

from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.core.errors import ConflictError, NotFoundError, ServiceUnavailableError
from app.core.logging import get_logger, log_event
from app.models import InterviewSession, Job
from app.models.enums import SessionStatus
from app.services import interview_context, session_service

logger = get_logger(__name__)

BATCH_SIZE = 5
MAX_QUESTIONS = 30

FINISHED = "This interview has ended or was cancelled."
LIMIT_REACHED = "This interview already has the most suggested questions."
NOTHING_WRITTEN = "No questions could be written. Please try again."
QUESTION_NOT_FOUND = "This question does not exist."

Reason = Literal["partly_met", "not_in_cv", "cv_claim"]

PROMPT = """\
You help an interviewer prepare questions for a live job interview.

Write exactly {count} interview questions for the candidate below. Base \
every question on this candidate's CV facts and screening results for this \
job; do not write general questions that could be asked of anyone.

Start with the requirements the candidate only partly meets or does not \
meet, especially must-haves. Then check claims the CV makes, such as a \
result, a responsibility or a technology used in a project.

For each question give:
- requirement_id: the id of the requirement it checks, such as "R2", or \
null if it checks no single requirement
- reason: "partly_met" if the requirement is partly met, "not_in_cv" if \
the CV does not show it, or "cv_claim" if it checks something the CV states
- question: one clear question the interviewer can read out, in under 30 \
words, speaking to the candidate as "you"
- why: why it is worth asking, in under 15 words, starting with a lower-case \
letter

Use job-related facts only. Never ask about age, gender, nationality, \
religion, ethnicity, marital status, health or family.
{already}
Interview details:
{context}
"""


class SuggestedQuestion(BaseModel):
    requirement_id: str | None = Field(
        default=None, description="The requirement it checks, such as R2"
    )
    reason: Reason
    question: str = Field(min_length=5, max_length=400)
    why: str = Field(min_length=2, max_length=200)


class QuestionBatch(BaseModel):
    questions: list[SuggestedQuestion]


def _open_session(db: Session, session_id: int) -> InterviewSession:
    session = session_service.get_session(db, session_id)
    if session.status not in (SessionStatus.SCHEDULED, SessionStatus.IN_PROGRESS):
        raise ConflictError(FINISHED)
    return session


def list_questions(db: Session, session_id: int) -> list[dict]:
    """The interview's suggested questions, oldest first."""
    return session_service.get_session(db, session_id).suggested_questions or []


def generate(db: Session, session_id: int) -> list[dict]:
    """Ask the AI for five more questions and save them with the interview.
    Returns every suggested question of the interview."""
    session = _open_session(db, session_id)
    existing = list(session.suggested_questions or [])
    if len(existing) >= MAX_QUESTIONS:
        raise ConflictError(LIMIT_REACHED)

    already = ""
    if existing:
        asked_before = "\n".join(f"- {item['question']}" for item in existing)
        already = (
            "\nThese questions were suggested already. Do not repeat them or "
            f"ask the same thing in other words:\n{asked_before}\n"
        )
    prompt = PROMPT.format(
        count=BATCH_SIZE,
        already=already,
        context=interview_context.describe(db, session),
    )
    batch = ai_client.generate_structured(prompt, QuestionBatch)
    if not batch.questions:
        raise ServiceUnavailableError(NOTHING_WRITTEN)

    job = db.get(Job, session.job_id)
    items = ((job.requirements or {}) if job else {}).get("items", [])
    requirement_texts = {item["id"]: item["text"] for item in items}
    next_id = max((item["id"] for item in existing), default=0) + 1
    added = []
    for offset, item in enumerate(batch.questions[:BATCH_SIZE]):
        requirement_id = item.requirement_id if item.requirement_id in requirement_texts else None
        added.append(
            {
                "id": next_id + offset,
                "requirement_id": requirement_id,
                "requirement": requirement_texts.get(requirement_id),
                "reason": item.reason,
                "question": item.question.strip(),
                "why": item.why.strip(),
                "asked": False,
            }
        )
    # A new list, so the change to the JSON column is saved.
    session.suggested_questions = existing + added
    db.commit()
    log_event(
        logger,
        "questions_suggested",
        session_id=session.id,
        added=len(added),
        total=len(session.suggested_questions),
    )
    return session.suggested_questions


def mark_asked(db: Session, session_id: int, question_id: int, asked: bool) -> list[dict]:
    """Mark one suggested question as asked, or not asked."""
    session = session_service.get_session(db, session_id)
    questions = [dict(item) for item in session.suggested_questions or []]
    question = next((item for item in questions if item["id"] == question_id), None)
    if question is None:
        raise NotFoundError(QUESTION_NOT_FOUND)
    question["asked"] = asked
    session.suggested_questions = questions
    db.commit()
    return questions
