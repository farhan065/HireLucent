"""Tests for CV intake checks. Google is never called and nothing is stored."""

import pytest

from app.core.errors import NotFoundError
from app.services import intake_service
from app.services.google_forms import FormResponse
from app.services.intake_service import read_cv
from app.services.text_extraction import FileTooLargeError, UnsupportedFileError

PDF = b"%PDF-1.7 sample"


def _response(**changes) -> FormResponse:
    values = {
        "response_id": "r1",
        "full_name": "Sample Person",
        "email": "sample@example.com",
        "file_id": "file-1",
        "file_name": "cv.pdf",
    }
    return FormResponse(**(values | changes))


def use_drive(monkeypatch: pytest.MonkeyPatch, result: bytes | Exception) -> list[str]:
    """Make the Drive download return the given content, or fail."""
    downloaded: list[str] = []

    def fake_download(file_id: str, max_mb: int) -> bytes:
        downloaded.append(file_id)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(intake_service.google_drive, "download_file", fake_download)
    return downloaded


def test_a_valid_application_is_downloaded(monkeypatch) -> None:
    downloaded = use_drive(monkeypatch, PDF)

    assert read_cv(_response()) == (".pdf", PDF)
    assert downloaded == ["file-1"]


@pytest.mark.parametrize(
    "changes",
    [
        {"email": ""},
        {"email": "not-an-email"},
        {"file_id": ""},
        {"file_name": "photo.png"},
        {"file_name": "notes.txt"},
    ],
)
def test_an_unusable_application_is_refused_before_downloading(
    monkeypatch, changes: dict
) -> None:
    downloaded = use_drive(monkeypatch, PDF)

    with pytest.raises(UnsupportedFileError):
        read_cv(_response(**changes))
    assert downloaded == []


def test_a_file_that_is_not_really_a_pdf_is_refused(monkeypatch) -> None:
    use_drive(monkeypatch, b"just some text")

    with pytest.raises(UnsupportedFileError):
        read_cv(_response())


@pytest.mark.parametrize(
    "error",
    [FileTooLargeError("too large"), NotFoundError("gone from Drive")],
)
def test_a_download_problem_is_passed_on(monkeypatch, error: Exception) -> None:
    use_drive(monkeypatch, error)

    with pytest.raises(type(error)):
        read_cv(_response())
