"""Reads a Google Form: checks an application form link and returns its details.

The app never creates or changes a form. It only reads, with the sign-in
saved by scripts/google_auth.py.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google.auth.exceptions import GoogleAuthError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import get_logger, log_event

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
NOT_CONNECTED = (
    "Google is not connected. Run the Google sign-in script, then try again."
)
SIGN_IN_EXPIRED = (
    "The Google sign-in has expired. Run the Google sign-in script again, then "
    "try again."
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
    has_file_upload: bool


def parse_form_id(link: str) -> str:
    """Take the form ID out of a form's editing address."""
    match = _EDIT_LINK.search(link)
    if match:
        return match.group(1)
    if _PUBLIC_LINK.search(link):
        raise FormLinkError(PUBLIC_LINK_GIVEN)
    raise FormLinkError(NOT_A_FORM_LINK)


def _forms_service() -> Any:
    token_file = Path(get_settings().google_token_file)
    if not token_file.exists():
        raise FormLinkError(NOT_CONNECTED)
    credentials = Credentials.from_authorized_user_file(str(token_file))
    return build("forms", "v1", credentials=credentials, cache_discovery=False)


def _has_file_upload(form: dict[str, Any]) -> bool:
    return any(
        "fileUploadQuestion" in item.get("questionItem", {}).get("question", {})
        for item in form.get("items", [])
    )


def get_form(link: str) -> FormInfo:
    """Check a form link and return the form's details.

    Raises FormLinkError, with a message for the interviewer, when the link
    is wrong or the form cannot be read.
    """
    form_id = parse_form_id(link)
    try:
        form = _forms_service().forms().get(formId=form_id).execute()
    except GoogleAuthError as exc:
        log_event(logger, "google_sign_in_expired", error_type=type(exc).__name__)
        raise FormLinkError(SIGN_IN_EXPIRED) from exc
    except HttpError as exc:
        log_event(logger, "form_read_failed", status=exc.status_code)
        if exc.status_code in (403, 404):
            raise FormLinkError(FORM_NOT_FOUND) from exc
        raise FormLinkError(FORM_UNAVAILABLE) from exc

    info = form.get("info", {})
    publish_state = form.get("publishSettings", {}).get("publishState", {})
    return FormInfo(
        form_id=form_id,
        title=info.get("title") or info.get("documentTitle") or "Untitled form",
        public_url=form["responderUri"],
        # Older forms do not report this, and they accept responses.
        accepts_responses=publish_state.get("isAcceptingResponses", True),
        has_file_upload=_has_file_upload(form),
    )
