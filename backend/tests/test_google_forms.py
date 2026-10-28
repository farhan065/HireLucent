"""Tests for reading an application form. Google is never called."""

from typing import Any

import pytest
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

from app.services import google_client, google_forms
from app.services.google_client import GoogleUnavailableError
from app.services.google_forms import (
    FormLinkError,
    get_form,
    list_responses,
    parse_form_id,
)

FORM_ID = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
EDIT_LINK = f"https://docs.google.com/forms/d/{FORM_ID}/edit"
FORM = {
    "formId": FORM_ID,
    "info": {"title": "Backend Engineer application"},
    "responderUri": "https://docs.google.com/forms/d/e/1FAIpQL/viewform",
    "items": [
        {"questionItem": {"question": {"textQuestion": {}}}},
        {"questionItem": {"question": {"fileUploadQuestion": {"folderId": "f"}}}},
    ],
}


class FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status
        self.reason = "error"


def use_google(monkeypatch: pytest.MonkeyPatch, result: Any) -> None:
    """Make the Forms API return a form, or raise the given error."""

    class Request:
        def execute(self) -> Any:
            if isinstance(result, Exception):
                raise result
            return result

    class Forms:
        def get(self, formId: str) -> Request:  # noqa: N803 (Google's name)
            return Request()

    class Service:
        def forms(self) -> Forms:
            return Forms()

    monkeypatch.setattr(google_forms, "google_service", lambda name, version: Service())


def test_the_form_id_is_read_from_the_editing_address() -> None:
    assert parse_form_id(EDIT_LINK) == FORM_ID
    assert parse_form_id(f"docs.google.com/forms/d/{FORM_ID}/edit#responses") == FORM_ID


def test_the_public_link_is_refused_with_an_explanation() -> None:
    with pytest.raises(FormLinkError, match="editing address"):
        parse_form_id("https://docs.google.com/forms/d/e/1FAIpQLSabc/viewform")


def test_other_links_are_refused() -> None:
    with pytest.raises(FormLinkError, match="not a Google Form link"):
        parse_form_id("https://example.com/apply")


def test_a_valid_form_returns_its_details(monkeypatch) -> None:
    use_google(monkeypatch, FORM)

    form = get_form(EDIT_LINK)

    assert form.form_id == FORM_ID
    assert form.title == "Backend Engineer application"
    assert form.public_url.endswith("/viewform")
    assert form.accepts_responses is True
    assert form.has_file_upload is True


def test_a_closed_form_without_file_upload_is_reported(monkeypatch) -> None:
    closed = {
        **FORM,
        "items": [],
        "publishSettings": {"publishState": {"isAcceptingResponses": False}},
    }
    use_google(monkeypatch, closed)

    form = get_form(EDIT_LINK)

    assert form.accepts_responses is False
    assert form.has_file_upload is False


def test_a_form_that_cannot_be_opened_gives_a_clear_message(monkeypatch) -> None:
    use_google(monkeypatch, HttpError(FakeResponse(404), b"{}"))

    with pytest.raises(FormLinkError, match="could not be opened"):
        get_form(EDIT_LINK)


def test_an_expired_sign_in_gives_a_clear_message(monkeypatch) -> None:
    use_google(monkeypatch, RefreshError("invalid_grant"))

    with pytest.raises(GoogleUnavailableError, match="expired"):
        get_form(EDIT_LINK)


def test_a_missing_sign_in_file_gives_a_clear_message(monkeypatch, tmp_path) -> None:
    settings = google_client.get_settings().model_copy(
        update={"google_token_file": str(tmp_path / "missing.json")}
    )
    monkeypatch.setattr(google_client, "get_settings", lambda: settings)

    with pytest.raises(GoogleUnavailableError, match="not connected"):
        get_form(EDIT_LINK)


QUESTIONS = {
    "items": [
        {"title": "Full name", "questionItem": {"question": {"questionId": "q-name"}}},
        {"title": "Email", "questionItem": {"question": {"questionId": "q-email"}}},
        {
            "title": "CV",
            "questionItem": {
                "question": {"questionId": "q-cv", "fileUploadQuestion": {"folderId": "f"}}
            },
        },
    ]
}


def _raw_response(response_id: str, name: str, email: str, file_id: str = "file-1") -> dict:
    return {
        "responseId": response_id,
        "answers": {
            "q-name": {"textAnswers": {"answers": [{"value": name}]}},
            "q-email": {"textAnswers": {"answers": [{"value": email}]}},
            "q-cv": {
                "fileUploadAnswers": {
                    "answers": [{"fileId": file_id, "fileName": "cv.pdf"}]
                }
            },
        },
    }


def use_responses(monkeypatch: pytest.MonkeyPatch, pages: list[dict]) -> None:
    """Make the Forms API return the form's questions and pages of responses."""
    remaining = list(pages)

    class Request:
        def __init__(self, result: dict) -> None:
            self.result = result

        def execute(self) -> dict:
            return self.result

    class Responses:
        def list(self, formId: str, pageToken: str | None) -> Request:  # noqa: N803
            return Request(remaining.pop(0))

    class Forms:
        def get(self, formId: str) -> Request:  # noqa: N803
            return Request(QUESTIONS)

        def responses(self) -> Responses:
            return Responses()

    class Service:
        def forms(self) -> Forms:
            return Forms()

    monkeypatch.setattr(google_forms, "google_service", lambda name, version: Service())


def test_responses_are_read_with_name_email_and_file(monkeypatch) -> None:
    use_responses(
        monkeypatch,
        [{"responses": [_raw_response("r1", " Sample Person ", "Sample@Example.com")]}],
    )

    responses = list_responses(FORM_ID)

    assert len(responses) == 1
    first = responses[0]
    assert (first.response_id, first.full_name) == ("r1", "Sample Person")
    assert first.email == "sample@example.com"
    assert (first.file_id, first.file_name) == ("file-1", "cv.pdf")


def test_every_page_of_responses_is_read(monkeypatch) -> None:
    use_responses(
        monkeypatch,
        [
            {"responses": [_raw_response("r1", "A", "a@example.com")], "nextPageToken": "p2"},
            {"responses": [_raw_response("r2", "B", "b@example.com")]},
        ],
    )

    assert [item.response_id for item in list_responses(FORM_ID)] == ["r1", "r2"]


def test_a_response_without_an_upload_has_no_file(monkeypatch) -> None:
    raw = _raw_response("r1", "A", "a@example.com")
    del raw["answers"]["q-cv"]
    use_responses(monkeypatch, [{"responses": [raw]}])

    assert list_responses(FORM_ID)[0].file_id == ""
