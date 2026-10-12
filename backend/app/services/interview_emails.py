"""The calendar invitation candidates receive about their interview.

Google Calendar emails it, so the candidate gets one email for each change:
the invitation, an "updated invitation" when the interview moves, and
Google's notice when it is cancelled, which shows the cancellation text.
Our text is the event's title and description, with the Join link first. They are fixed templates, not
written by AI, so every candidate gets the same clear wording.
"""

from dataclasses import dataclass
from datetime import datetime

from app.core.config import get_settings
from app.services.interview_times import describe

PREVIEW_LINK = "[private link]"
SIGNATURE = "Best regards,\nHireLucent Careers"
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


def _description(link: str, paragraphs: list[str]) -> str:
    opens = get_settings().join_opens_minutes_before
    tips = "Before the interview:\n" + "\n".join(f"- {tip}" for tip in BEFORE_YOU_JOIN)
    return "\n\n".join(
        [
            f"Join the interview: {link}\n"
            f"The Join button opens {opens} minutes before the start. "
            "This link is personal. Please do not share it.",
            *paragraphs,
            tips,
            SIGNATURE,
        ]
    )


def _length(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() // 60)


def invitation(
    candidate_name: str, job_title: str, start: datetime, end: datetime, link: str
) -> Invitation:
    return Invitation(
        title=calendar_title(job_title),
        description=_description(
            link,
            [
                f"Hello {candidate_name},",
                f"Thank you for applying for the {job_title} role. We would like to "
                f"invite you to a {_length(start, end)}-minute video interview.",
                f"When: {describe(start, end)}\n"
                "Your calendar shows the time in your own time zone.",
            ],
        ),
    )


def moved(
    candidate_name: str, job_title: str, start: datetime, end: datetime, link: str
) -> Invitation:
    return Invitation(
        title=calendar_title(job_title),
        description=_description(
            link,
            [
                f"Hello {candidate_name},",
                f"Your interview for the {job_title} role has moved to a new time. "
                "Please use the link above. The link in the earlier invitation no "
                "longer works.",
                f"New time: {describe(start, end)}\n"
                "Your calendar shows the time in your own time zone.",
            ],
        ),
    )


def cancelled(candidate_name: str, job_title: str, start: datetime, end: datetime) -> str:
    """The description shown in Google's cancellation notice. No link."""
    return "\n\n".join(
        [
            f"Hello {candidate_name},",
            f"Your interview for the {job_title} role on {describe(start, end)} has "
            "been cancelled. The interview link no longer works.",
            "The hiring team will contact you about the next steps.",
            SIGNATURE,
        ]
    )
