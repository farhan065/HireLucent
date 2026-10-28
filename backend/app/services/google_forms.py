"""Reads a Google Form: its details, and the applications submitted through it.

The app never creates or changes a form. It only reads, with the sign-in
saved by scripts/google_auth.py.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from google.auth.exceptions import GoogleAuthError
from googleapiclient.errors import HttpError

from app.core.errors import AppError
from app.core.logging import get_logger, log_event
from app.services.google_client import (
    SIGN_IN_EXPIRED,
    GoogleUnavailableError,
    google_service,
)

logger = get_logger(__name__)

# The address in the browser bar while editing a form:
# https://docs.google.com/forms/d/<form id>/edit
_EDIT_LINK = re.compile(r"docs\.google\.com/forms/d/(?!e/)([A-Za-z0-9_-]{20,})")
_PUBLIC_LINK = re.compile(r"docs\.google\.com/forms/d/e/|forms\.gle/")

NOT_A_FORM_LINK = "That is not a Google Form link."
PUBLIC_LINK_GIVEN = (
    "That is the link candidates use. Paste the form's editing address instead: "
    "open the form in Google Forms and copy the address from the browser bar."
)
FORM_NOT_FOUND = (
    "The form could not be opened. Check that it belongs to the connected "
    "Google account."
)
FORM_UNAVAILABLE = "Google Forms could not be reached. Please try again."


class FormLinkError(AppError):
    """A form link that cannot be used. The message is safe to show."""

    code = "form_link"


@dataclass(frozen=True)
class FormInfo:
    form_id: str
    title: str
    # The address candidates open to apply.
    public_url: str
    accepts_responses: bool
    # A file upload question for the CV (any upload not asking for the photo).
    has_file_upload: bool
    # Candidate identification (F7): a required photo upload and a required
    # consent question.
    has_photo_upload: bool = False
    has_consent_question: bool = False


def parse_form_id(link: str) -> str:
    """Take the form ID out of a form's editing address."""
    match = _EDIT_LINK.search(link)
    if match:
        return match.group(1)
    if _PUBLIC_LINK.search(link):
        raise FormLinkError(PUBLIC_LINK_GIVEN)
    raise FormLinkError(NOT_A_FORM_LINK)


# The photo and consent questions are found by a word in their title, the
# same way as the name and email questions.
PHOTO_WORD = "photo"
CONSENT_WORD = "consent"


def _questions(form: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Each question with its title in lower case."""
    return [
        (item.get("title", "").lower(), item["questionItem"]["question"])
        for item in form.get("items", [])
        if "questionItem" in item
    ]


def _has_file_upload(form: dict[str, Any]) -> bool:
    return any(
        "fileUploadQuestion" in question and PHOTO_WORD not in title
        for title, question in _questions(form)
    )


def _has_required(form: dict[str, Any], word: str, kind: str | None = None) -> bool:
    """Whether a required question has the word in its title (and is of
    the given kind, such as a file upload)."""
    return any(
        word in title and question.get("required", False) and (kind is None or kind in question)
        for title, question in _questions(form)
    )


def _read(request: Any) -> dict[str, Any]:
    """Run a Forms API request, turning Google's errors into clear messages."""
    try:
        return request.execute()
    except GoogleAuthError as exc:
        log_event(logger, "google_sign_in_expired", error_type=type(exc).__name__)
        raise GoogleUnavailableError(SIGN_IN_EXPIRED) from exc
    except HttpError as exc:
        log_event(logger, "form_read_failed", status=exc.status_code)
        if exc.status_code in (403, 404):
            raise FormLinkError(FORM_NOT_FOUND) from exc
        raise GoogleUnavailableError(FORM_UNAVAILABLE) from exc


def get_form(link: str) -> FormInfo:
    """Check a form link and return the form's details.

    Raises an error with a message for the interviewer when the link is
    wrong or the form cannot be read.
    """
    form_id = parse_form_id(link)
    form = _read(google_service("forms", "v1").forms().get(formId=form_id))

    info = form.get("info", {})
    publish_state = form.get("publishSettings", {}).get("publishState", {})
    return FormInfo(
        form_id=form_id,
        title=info.get("title") or info.get("documentTitle") or "Untitled form",
        public_url=form["responderUri"],
        # Older forms do not report this, and they accept responses.
        accepts_responses=publish_state.get("isAcceptingResponses", True),
        has_file_upload=_has_file_upload(form),
        has_photo_upload=_has_required(form, PHOTO_WORD, "fileUploadQuestion"),
        has_consent_question=_has_required(form, CONSENT_WORD),
    )


@dataclass(frozen=True)
class FormResponse:
    """One submission of the application form."""

    response_id: str
    full_name: str
    email: str
    # The uploaded CV in Google Drive. Empty if nothing was uploaded.
    file_id: str
    file_name: str
    # The uploaded photo, whether the consent question was answered, and
    # when the form was sent (F7). Empty for forms without these questions.
    photo_file_id: str = ""
    photo_file_name: str = ""
    consent: bool = False
    submitted_at: datetime | None = None


def _question_ids(form: dict[str, Any], word: str) -> set[str]:
    """IDs of the questions whose title contains a word, such as "email"."""
    return {
        item["questionItem"]["question"]["questionId"]
        for item in form.get("items", [])
        if "questionItem" in item and word in item.get("title", "").lower()
    }


def _text_answer(answers: dict[str, Any], question_ids: set[str]) -> str:
    for question_id in question_ids:
        values = answers.get(question_id, {}).get("textAnswers", {}).get("answers", [])
        if values:
            return values[0].get("value", "").strip()
    return ""


def _uploads(answers: dict[str, Any], question_ids: set[str] | None) -> list[dict[str, Any]]:
    """The uploaded files: of the given questions, or of all of them."""
    return [
        upload
        for question_id, answer in answers.items()
        if question_ids is None or question_id in question_ids
        for upload in answer.get("fileUploadAnswers", {}).get("answers", [])
    ]


def _submitted(raw: dict[str, Any]) -> datetime | None:
    value = raw.get("lastSubmittedTime") or raw.get("createTime")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
    except ValueError:
        return None


def _to_response(
    raw: dict[str, Any],
    name_ids: set[str],
    email_ids: set[str],
    photo_ids: set[str] | None = None,
    consent_ids: set[str] | None = None,
) -> FormResponse:
    answers = raw.get("answers", {})
    photo_ids = photo_ids or set()
    # The CV is any upload that is not the photo.
    cvs = [
        upload
        for question_id, answer in answers.items()
        if question_id not in photo_ids
        for upload in answer.get("fileUploadAnswers", {}).get("answers", [])
    ]
    upload = cvs[0] if cvs else {}
    photos = _uploads(answers, photo_ids) if photo_ids else []
    photo = photos[0] if photos else {}
    return FormResponse(
        response_id=raw["responseId"],
        full_name=_text_answer(answers, name_ids),
        # A form set to collect emails reports the address separately.
        email=(_text_answer(answers, email_ids) or raw.get("respondentEmail", "")).lower(),
        file_id=upload.get("fileId", ""),
        file_name=upload.get("fileName", ""),
        photo_file_id=photo.get("fileId", ""),
        photo_file_name=photo.get("fileName", ""),
        consent=bool(consent_ids) and bool(_text_answer(answers, consent_ids)),
        submitted_at=_submitted(raw),
    )


def list_responses(form_id: str) -> list[FormResponse]:
    """Every submission of a form, oldest first."""
    forms = google_service("forms", "v1").forms()
    form = _read(forms.get(formId=form_id))
    name_ids = _question_ids(form, "name")
    email_ids = _question_ids(form, "email")
    photo_ids = _question_ids(form, PHOTO_WORD)
    consent_ids = _question_ids(form, CONSENT_WORD)

    responses: list[FormResponse] = []
    page_token = None
    while True:
        page = _read(forms.responses().list(formId=form_id, pageToken=page_token))
        responses += [
            _to_response(raw, name_ids, email_ids, photo_ids, consent_ids)
            for raw in page.get("responses", [])
        ]
        page_token = page.get("nextPageToken")
        if not page_token:
            return responses
