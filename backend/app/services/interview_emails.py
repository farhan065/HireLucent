"""The emails and calendar text sent to candidates about their interview.

They are fixed templates, not written by AI, so every candidate gets the
same clear wording. Names and titles are escaped in the HTML version.
"""

from dataclasses import dataclass
from datetime import datetime
from html import escape

from app.core.config import get_settings
from app.services.interview_times import describe

PREVIEW_LINK = "[private link]"
SIGNATURE = "Best regards,\nHireLucent Careers"


@dataclass(frozen=True)
class Email:
    subject: str
    text: str
    html: str


def calendar_title(job_title: str) -> str:
    return f"Interview: {job_title} (HireLucent)"


def calendar_description(job_title: str, link: str) -> str:
    minutes = get_settings().join_opens_minutes_before
    return (
        f"Video interview for the {job_title} role.\n\n"
        f"Join: {link}\n"
        f"The Join button opens {minutes} minutes before the start.\n\n"
        "This link is personal. Please do not share it."
    )


def _before_you_join() -> list[str]:
    return [
        "Use a computer with a camera and microphone, and a recent Chrome, "
        "Edge or Firefox.",
        "Find a quiet place. Headphones help.",
        "What is said in the interview is turned into a written transcript for "
        "the hiring team. The audio and video are not recorded or kept. You will "
        "be asked to agree to this before you join.",
    ]


def _build(subject: str, paragraphs: list[str], link: str | None, tips: bool) -> Email:
    """Build the plain-text and HTML versions from the same parts."""
    text_parts = list(paragraphs)
    html_parts = [f"<p>{escape(part).replace(chr(10), '<br>')}</p>" for part in paragraphs]
    if link:
        text_parts.append(f"Join: {link}")
        html_parts.append(
            f'<p><a href="{escape(link)}" style="display:inline-block;padding:12px 22px;'
            "border-radius:999px;background:#1557e0;color:#ffffff;"
            'text-decoration:none;font-weight:bold">Join interview</a></p>'
            f'<p style="font-size:13px;color:#51607a">Or open: {escape(link)}</p>'
        )
    if tips:
        items = _before_you_join()
        text_parts.append("Before the interview:\n" + "\n".join(f"- {item}" for item in items))
        html_parts.append(
            "<p><strong>Before the interview</strong></p><ul>"
            + "".join(f"<li>{escape(item)}</li>" for item in items)
            + "</ul>"
        )
        text_parts.append("This link is personal. Please do not share it.")
        html_parts.append("<p>This link is personal. Please do not share it.</p>")
    text_parts.append(SIGNATURE)
    html_parts.append("<p>Best regards,<br>HireLucent Careers</p>")
    return Email(
        subject=subject,
        text="\n\n".join(text_parts),
        html='<div style="font-family:Arial,sans-serif;font-size:15px;color:#0b1f4b">'
        + "".join(html_parts)
        + "</div>",
    )


def invitation(
    candidate_name: str, job_title: str, start: datetime, end: datetime, link: str
) -> Email:
    minutes = int((end - start).total_seconds() // 60)
    opens = get_settings().join_opens_minutes_before
    return _build(
        f"Interview invitation: {job_title}",
        [
            f"Hello {candidate_name},",
            f"Thank you for applying for the {job_title} role. We would like to "
            "invite you to a video interview.",
            f"When: {describe(start, end)}\nLength: {minutes} minutes",
            f"The Join button opens {opens} minutes before the start. Your "
            "calendar invitation shows the time in your own time zone.",
        ],
        link,
        tips=True,
    )


def rescheduled(
    candidate_name: str, job_title: str, start: datetime, end: datetime, link: str
) -> Email:
    return _build(
        f"Your interview has moved: {job_title}",
        [
            f"Hello {candidate_name},",
            f"Your interview for the {job_title} role has moved to a new time.",
            f"New time: {describe(start, end)}",
            "Please use the new link below. The link from the earlier email no "
            "longer works.",
        ],
        link,
        tips=True,
    )


def cancelled(
    candidate_name: str, job_title: str, start: datetime, end: datetime
) -> Email:
    return _build(
        f"Your interview has been cancelled: {job_title}",
        [
            f"Hello {candidate_name},",
            f"Your interview for the {job_title} role on {describe(start, end)} "
            "has been cancelled.",
            "The hiring team will contact you about the next steps.",
        ],
        None,
        tips=False,
    )
