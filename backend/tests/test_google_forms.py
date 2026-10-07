"""Tests for reading an application form. Google is never called."""

from typing import Any

import pytest
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

from app.services import google_forms
from app.services.google_forms import FormLinkError, get_form, parse_form_id

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

    monkeypatch.setattr(google_forms, "_forms_service", Service)


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

    with pytest.raises(FormLinkError, match="expired"):
        get_form(EDIT_LINK)


def test_a_missing_sign_in_file_gives_a_clear_message(monkeypatch, tmp_path) -> None:
    settings = google_forms.get_settings().model_copy(
        update={"google_token_file": str(tmp_path / "missing.json")}
    )
    monkeypatch.setattr(google_forms, "get_settings", lambda: settings)

    with pytest.raises(FormLinkError, match="not connected"):
        get_form(EDIT_LINK)
