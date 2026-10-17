"""The calendar invitation candidates receive about their interview.

Google Calendar emails it, so the candidate gets one email for each change:
the invitation, an "updated invitation" when the interview moves, and
Google's notice when it is cancelled, which shows the cancellation text.

Our text is the event's title and description. They are fixed templates,
not written by AI. Only the message paragraph can be changed by the
interviewer; the greeting, the time, the Join link, the tips and the
signature are always added by the template, in this order:

    Hello -> message -> When -> Join link -> tips -> signature
"""

import re
from dataclasses import dataclass
from datetime import datetime

from app.core.config import get_settings
from app.services.interview_times import describe

INVITATION = "invitation"
MOVED = "moved"
CANCELLED = "cancelled"

PREVIEW_LINK = "[private link]"
SIGNATURE = "Best regards,\nHireLucent Careers"
MAX_MESSAGE_LENGTH = 1500
HTML_TAG = re.compile(r"<\s*/?\s*[a-zA-Z!][^>]*>")
BEFORE_YOU_JOIN = [
    "Use a computer with a camera and microphone, and a recent Chrome, Edge or Firefox.",
    "Find a quiet place. Headphones help.",
    "What is said in the interview is turned into a written transcript for the "
    "hiring team. The audio and video are not recorded or kept. You will be asked "
    "to agree to this before you join.",
]


@dataclass(frozen=True)
class Invitation:
    """The calendar event's title and description."""

    title: str
    description: str


def calendar_title(job_title: str) -> str:
    return f"HireLucent video interview – {job_title}"


def clean_message(text: str) -> str:
    """The interviewer's message as tidy plain text. Raises ValueError if it
    is empty, too long or contains HTML."""
    lines = [line.rstrip() for line in text.strip().splitlines()]
    message = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    if not message:
        raise ValueError("The message to the candidate cannot be empty.")
    if len(message) > MAX_MESSAGE_LENGTH:
        raise ValueError(
            f"The message to the candidate can be at most {MAX_MESSAGE_LENGTH} characters."
        )
    if HTML_TAG.search(message):
        raise ValueError("The message to the candidate must be plain text, without HTML.")
    return message


def default_message(kind: str, job_title: str, start: datetime, end: datetime) -> str:
    """The message used when the interviewer has not written their own."""
    if kind == INVITATION:
        return (
            f"Thank you for applying for the {job_title} role. We would like to "
            f"invite you to a {_length(start, end)}-minute video interview."
        )
    if kind == MOVED:
        return f"Your interview for the {job_title} role has moved to a new time."
    return "The hiring team will contact you about the next steps."


def _length(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() // 60)


def _join(link: str, note: str = "") -> str:
    opens = get_settings().join_opens_minutes_before
    return (
        f"Join the interview: {link}\n"
        f"The Join button opens {opens} minutes before the start. "
        f"This link is personal. Please do not share it.{note}"
    )


def _tips() -> str:
    return "Before the interview:\n" + "\n".join(f"- {tip}" for tip in BEFORE_YOU_JOIN)


def invitation(
    candidate_name: str,
    job_title: str,
    start: datetime,
    end: datetime,
    link: str,
    message: str | None = None,
) -> Invitation:
    return Invitation(
        title=calendar_title(job_title),
        description="\n\n".join(
            [
                f"Hello {candidate_name},",
                message or default_message(INVITATION, job_title, start, end),
                f"When: {describe(start, end)}\n"
                "Your calendar shows the time in your own time zone.",
                _join(link),
                _tips(),
                SIGNATURE,
            ]
        ),
    )


def moved(
    candidate_name: str,
    job_title: str,
    start: datetime,
    end: datetime,
    link: str,
    message: str | None = None,
) -> Invitation:
    return Invitation(
        title=calendar_title(job_title),
        description="\n\n".join(
            [
                f"Hello {candidate_name},",
                message or default_message(MOVED, job_title, start, end),
                f"New time: {describe(start, end)}\n"
                "Your calendar shows the time in your own time zone.",
                _join(link, " The link in the earlier invitation no longer works."),
                _tips(),
                SIGNATURE,
            ]
        ),
    )


def cancelled(
    candidate_name: str,
    job_title: str,
    start: datetime,
    end: datetime,
    message: str | None = None,
) -> str:
    """The description shown in Google's cancellation notice. No link."""
    return "\n\n".join(
        [
            f"Hello {candidate_name},",
            f"Your interview for the {job_title} role on {describe(start, end)} has "
            "been cancelled. The interview link no longer works.",
            message or default_message(CANCELLED, job_title, start, end),
            SIGNATURE,
        ]
    )


def preview(
    kind: str,
    candidate_name: str,
    job_title: str,
    start: datetime,
    end: datetime,
    message: str | None = None,
) -> dict[str, str]:
    """The email as the candidate will see it, with "[private link]" in
    place of the link, and the message used in it."""
    used = message or default_message(kind, job_title, start, end)
    if kind == INVITATION:
        text = invitation(candidate_name, job_title, start, end, PREVIEW_LINK, used).description
    elif kind == MOVED:
        text = moved(candidate_name, job_title, start, end, PREVIEW_LINK, used).description
    else:
        text = cancelled(candidate_name, job_title, start, end, used)
    return {
        "subject": calendar_title(job_title),
        "text": text,
        "message": used,
        "default_message": default_message(kind, job_title, start, end),
    }
