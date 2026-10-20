"""Tests for candidate identification (F7): the interview PIN, the identity
photo check, enrolment at Fetch CVs and the form's photo and consent
questions. No face photo is used: the face checks are replaced with
stand-ins, except where a blank picture is enough."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

import app.models.interview as interview_module
from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError, ServiceUnavailableError, UnauthorizedError
from app.models import Candidate, InterviewSession, Job
from app.models.enums import CandidateStatus, FaceStatus, IdentityResult, SessionStatus
from app.services import (
    face_models,
    face_service,
    google_forms,
    identity_service,
    intake_service,
    interview_emails,
    join_service,
    pin_service,
    scheduling_service,
    session_service,
)
from app.services.google_forms import FormResponse

NOW = datetime(2026, 10, 21, 8, 55, tzinfo=timezone.utc)
START = NOW + timedelta(minutes=5)
END = START + timedelta(minutes=45)
TOKEN = "a-private-token-for-the-tests"
LINK = "http://localhost:3000/interview/secret-token"


def _code(*values: float) -> bytes:
    """A face code made of the given numbers (a real one has 128)."""
    return np.array(values, dtype=np.float32).tobytes()


INVITED = _code(1, 0, 0)
LOOKALIKE = _code(0.6, 0.8, 0)


def _candidate(candidate_id=5, code=INVITED, status=FaceStatus.ENROLLED, name="Nadia Karim"):
    return Candidate(
        id=candidate_id,
        job_id=2,
        full_name=name,
        email=f"c{candidate_id}@example.com",
        status=CandidateStatus.INTERVIEW_SCHEDULED,
        face_code=code,
        face_status=status,
    )


def _session(candidate=None, pin="48291067", status=SessionStatus.SCHEDULED):
    session = InterviewSession(
        id=9,
        candidate_id=5,
        job_id=2,
        scheduled_start=START,
        scheduled_end=END,
        join_token_hash=session_service.hash_token(TOKEN),
        status=status,
        calendar_event_id="event-1",
        pin_failed_attempts=0,
    )
    session.candidate = candidate or _candidate()
    if pin:
        session.pin_hash = pin_service.hash_password(pin)
    return session


class FakeDB:
    """Holds one interview and the job's other applicants."""

    def __init__(self, session=None, others=()):
        self.session = session
        self.others = list(others)
        self.commits = 0

    def scalar(self, _query):
        return self.session

    def scalars(self, _query):
        return iter(self.others)

    def get(self, model, key):
        if model is Job:
            return Job(id=2, title="Backend Engineer")
        if model is Candidate:
            return next((c for c in self.others if c.id == key), None)
        return self.session if self.session and key == self.session.id else None

    def commit(self):
        self.commits += 1


# --- The PIN ---


def test_a_new_pin_has_eight_digits_and_only_its_hash_is_stored() -> None:
    session = _session(pin=None)

    pin = pin_service.new_pin(session)

    assert len(pin) == 8 and pin.isdigit()
    assert pin not in session.pin_hash
    assert pin_service.shown(pin) == f"{pin[:4]} {pin[4:]}"


def test_the_right_pin_passes_with_or_without_the_space() -> None:
    session = _session()

    assert pin_service.check(session, "4829 1067", NOW).result == pin_service.OK
    assert pin_service.check(session, "48291067", NOW).result == pin_service.OK


def test_a_wrong_pin_says_how_many_tries_are_left() -> None:
    session = _session()

    result = pin_service.check(session, "11112222", NOW)

    assert result.result == pin_service.WRONG and result.tries_left == 4


def test_the_fifth_wrong_try_locks_the_link_even_for_the_right_pin() -> None:
    session = _session()
    for _ in range(4):
        pin_service.check(session, "11112222", NOW)

    locked = pin_service.check(session, "11112222", NOW)

    assert locked.result == pin_service.LOCKED
    assert locked.locked_until == NOW + timedelta(minutes=15)
    assert pin_service.check(session, "48291067", NOW).result == pin_service.LOCKED
    later = NOW + timedelta(minutes=16)
    assert pin_service.check(session, "48291067", later).result == pin_service.OK


def test_a_new_pin_clears_the_lock() -> None:
    session = _session()
    session.pin_locked_until = NOW + timedelta(minutes=10)

    pin_service.new_pin(session)

    assert not pin_service.is_locked(session, NOW)


# --- The invitation ---


def test_the_pin_is_right_under_the_join_link() -> None:
    text = interview_emails.invitation(
        "Test", "Backend Engineer", START, END, LINK, pin="4829 1067"
    ).description

    assert f"Join the interview: {LINK}\nInterview PIN: 4829 1067 (you will be asked" in text
    assert "one photo is taken to confirm it is you" in text


def test_the_preview_hides_the_link_and_the_pin() -> None:
    preview = interview_emails.preview(
        interview_emails.INVITATION, "Test", "Backend Engineer", START, END
    )

    assert "[private link]\nInterview PIN: [private PIN]" in preview["text"]


def test_the_new_pin_email_keeps_the_time_and_retires_the_old_link() -> None:
    preview = interview_emails.preview(
        interview_emails.NEW_PIN, "Test", "Backend Engineer", START, END
    )

    assert "new PIN and join link" in preview["text"]
    assert "When: " in preview["text"]
    assert "link and PIN in the earlier invitation no longer work" in preview["text"]


# --- Send a new PIN ---


@pytest.fixture()
def google(monkeypatch: pytest.MonkeyPatch) -> dict:
    record = {"calls": [], "fail": False}

    def fake(tool, arguments):
        record["calls"].append((tool, arguments))
        if record["fail"]:
            raise ServiceUnavailableError("Google down")
        return {}

    monkeypatch.setattr(scheduling_service, "_google", fake)
    return record


def test_a_new_pin_updates_the_invitation_with_a_new_link(google) -> None:
    session = _session()
    old_link, old_pin = session.join_token_hash, session.pin_hash

    scheduling_service.send_new_pin(FakeDB(session), 9)

    tool, arguments = google["calls"][0]
    assert tool == "update_calendar_event"
    assert "Interview PIN: " in arguments["description"]
    assert session.join_token_hash != old_link and session.pin_hash != old_pin


def test_when_google_fails_the_old_link_and_pin_still_work(google) -> None:
    google["fail"] = True
    session = _session()
    old_link, old_pin = session.join_token_hash, session.pin_hash

    with pytest.raises(ServiceUnavailableError, match="old link and PIN still work"):
        scheduling_service.send_new_pin(FakeDB(session), 9)

    assert session.join_token_hash == old_link and session.pin_hash == old_pin


def test_no_new_pin_for_a_finished_interview(google) -> None:
    with pytest.raises(ConflictError):
        scheduling_service.send_new_pin(FakeDB(_session(status=SessionStatus.COMPLETED)), 9)


# --- Joining with the PIN ---


def test_the_link_says_a_pin_is_needed() -> None:
    assert join_service.link_info(FakeDB(_session()), TOKEN, now=NOW)["pin_required"] is True
    assert join_service.link_info(FakeDB(_session(pin=None)), TOKEN, now=NOW)["pin_required"] is False


def test_joining_needs_the_right_pin() -> None:
    session = _session()

    with pytest.raises(UnauthorizedError, match="PIN is not right"):
        join_service.enter(FakeDB(session), TOKEN, now=NOW, pin="11112222")
    assert session.consent_given_at is None

    join_service.enter(FakeDB(session), TOKEN, now=NOW, pin="4829 1067")
    assert session.consent_given_at == NOW


def test_a_locked_link_cannot_be_joined() -> None:
    session = _session()
    session.pin_locked_until = NOW + timedelta(minutes=5)

    with pytest.raises(ConflictError, match="locked"):
        join_service.enter(FakeDB(session), TOKEN, now=NOW, pin="48291067")


def test_an_interview_without_a_pin_joins_as_before() -> None:
    session = _session(pin=None)

    join_service.enter(FakeDB(session), TOKEN, now=NOW)

    assert session.consent_given_at == NOW
    assert join_service.needs_photo(FakeDB(session), TOKEN) is False


def test_the_pin_check_of_an_ended_interview_says_the_link_is_gone() -> None:
    with pytest.raises(NotFoundError):
        join_service.check_pin(
            FakeDB(_session(status=SessionStatus.CANCELLED)), TOKEN, "48291067", now=NOW
        )


# --- The identity decision ---


@pytest.mark.parametrize(
    ("score", "result"),
    [(0.61, "verified"), (0.50, "verified"), (0.44, "low"), (0.363, "low"), (0.30, "very_low")],
)
def test_the_bands_come_from_the_face_test(score, result) -> None:
    assert identity_service.decide(score, None)["result"] == result


def test_another_applicant_who_matches_better_is_flagged() -> None:
    check = identity_service.decide(0.21, (12, 0.58))

    assert check["result"] == IdentityResult.OTHER_APPLICANT
    assert check["other_candidate_id"] == 12 and check["other_score"] == 0.58


def test_another_applicant_below_the_verified_band_is_ignored() -> None:
    assert identity_service.decide(0.40, (12, 0.45))["result"] == "low"


def test_the_invited_candidate_matching_best_is_verified() -> None:
    assert identity_service.decide(0.62, (12, 0.55))["result"] == "verified"


def test_the_similarity_of_face_codes() -> None:
    assert face_service.similarity(INVITED, INVITED) == pytest.approx(1.0)
    assert face_service.similarity(INVITED, LOOKALIKE) == pytest.approx(0.6)


# --- The identity photo ---


def _faces(monkeypatch, *checks: face_service.FaceCheck) -> None:
    results = iter(checks)
    monkeypatch.setattr(face_service, "check_photo", lambda content: next(results))


def test_the_photo_is_compared_and_only_the_result_kept(monkeypatch) -> None:
    session = _session()
    _faces(monkeypatch, face_service.FaceCheck(code=INVITED))

    state, _ = identity_service.check_photo(FakeDB(session), session, b"jpeg", NOW)

    assert state == identity_service.DONE
    assert session.identity_check["result"] == "verified"
    assert session.identity_check["score"] == 1.0
    assert "code" not in str(session.identity_check)


def test_a_photo_that_looks_like_another_applicant_names_them(monkeypatch) -> None:
    session = _session()
    other = _candidate(12, code=_code(0, 1, 0), name="Tanvir Ahmed")
    db = FakeDB(session, others=[other])
    session.candidate.face_code = _code(0, 0, 1)
    _faces(monkeypatch, face_service.FaceCheck(code=_code(0, 1, 0)))

    identity_service.check_photo(db, session, b"jpeg", NOW)

    # The interview finds the other candidate by id, as the database would.
    monkeypatch.setattr(interview_module, "object_session", lambda _instance: db)
    identity = session.identity
    assert identity["result"] == "other_applicant"
    assert identity["other_candidate_name"] == "Tanvir Ahmed"


def test_an_unusable_photo_can_be_retried_twice_then_joins_unchecked(monkeypatch) -> None:
    session = _session()
    bad = face_service.FaceCheck(problem=face_service.TOO_DARK)
    _faces(monkeypatch, bad, bad, bad)
    db = FakeDB(session)

    assert identity_service.check_photo(db, session, b"1", NOW) == (identity_service.RETRY, 2)
    assert identity_service.check_photo(db, session, b"2", NOW) == (identity_service.RETRY, 1)
    assert identity_service.check_photo(db, session, b"3", NOW) == ("skipped", None)
    assert session.identity_check["result"] == "not_checked"
    assert identity_service.needs_photo(session) is False


def test_without_an_application_photo_the_check_says_why(monkeypatch) -> None:
    candidate = _candidate(code=None, status=FaceStatus.PHOTO_UNUSABLE)
    candidate.face_problem = face_service.TOO_BLURRY
    session = _session(candidate)
    _faces(monkeypatch, face_service.FaceCheck(code=INVITED))

    identity_service.check_photo(FakeDB(session), session, b"jpeg", NOW)

    assert session.identity_check["result"] == "not_checked"
    assert "too blurry" in session.identity_check["reason"]


def test_skipping_records_the_reason() -> None:
    session = _session()

    identity_service.skip(FakeDB(session), session, identity_service.NO_CAMERA, NOW)

    assert session.identity_check["result"] == "not_checked"
    assert "camera" in session.identity_check["reason"]


def test_the_interviewer_sees_pending_then_not_taken() -> None:
    session = _session()
    assert session.identity == {"result": "pending"}

    session.status = SessionStatus.IN_PROGRESS
    assert session.identity["result"] == "not_checked"
    assert _session(pin=None).identity is None


def test_a_check_happens_only_once(monkeypatch) -> None:
    session = _session()
    session.identity_check = {"result": "verified", "score": 0.6}
    monkeypatch.setattr(face_service, "check_photo", lambda content: pytest.fail("checked again"))

    assert identity_service.check_photo(FakeDB(session), session, b"x", NOW)[0] == "done"


# --- Face photos (no models needed) ---


def test_a_file_that_is_not_an_image_is_refused() -> None:
    assert face_service.check_photo(b"not an image").problem == face_service.NOT_AN_IMAGE


def test_a_stored_photo_is_a_small_jpeg() -> None:
    image = np.full((1600, 1200, 3), 128, dtype=np.uint8)

    data = face_service.jpeg_for_storage(image)

    stored = face_service.read_image(data)
    assert data[:2] == b"\xff\xd8"
    assert max(stored.shape[:2]) == face_service.STORED_SIDE


def _models_ready() -> bool:
    folder = Path(get_settings().face_models_dir)
    return all(face_models.is_valid(folder / name, name) for name in face_models.URLS)


@pytest.mark.skipif(not _models_ready(), reason="The face models are not downloaded here.")
def test_a_photo_without_a_face_is_refused() -> None:
    blank = face_service.jpeg_for_storage(np.full((480, 640, 3), 200, dtype=np.uint8))

    assert face_service.check_photo(blank).problem == face_service.NO_FACE


# --- The form and enrolment ---


def _form_item(title, question):
    return {"title": title, "questionItem": {"question": {"questionId": title[:4], **question}}}


def test_the_form_needs_a_required_photo_and_consent(monkeypatch) -> None:
    form = {
        "formId": "f",
        "responderUri": "https://docs.google.com/forms/d/e/x/viewform",
        "items": [
            _form_item("Upload your CV", {"fileUploadQuestion": {}, "required": True}),
            _form_item("Recent photo", {"fileUploadQuestion": {}, "required": True}),
            _form_item("Biometric consent", {"choiceQuestion": {}, "required": False}),
        ],
    }

    class Service:
        def forms(self):
            return self

        def get(self, formId):  # noqa: N803 (Google's name)
            return self

        def execute(self):
            return form

    monkeypatch.setattr(google_forms, "google_service", lambda name, version: Service())
    info = google_forms.get_form("https://docs.google.com/forms/d/1AbCdEfGhIjKlMnOpQrStUv/edit")

    assert info.has_file_upload and info.has_photo_upload
    assert info.has_consent_question is False


def test_a_response_reads_the_cv_photo_and_consent_apart() -> None:
    raw = {
        "responseId": "r1",
        "lastSubmittedTime": "2026-10-12T10:00:00Z",
        "answers": {
            "cv": {"fileUploadAnswers": {"answers": [{"fileId": "cv-1", "fileName": "cv.pdf"}]}},
            "ph": {"fileUploadAnswers": {"answers": [{"fileId": "ph-1", "fileName": "me.jpg"}]}},
            "co": {"textAnswers": {"answers": [{"value": "I agree"}]}},
        },
    }

    response = google_forms._to_response(raw, set(), set(), {"ph"}, {"co"})

    assert (response.file_id, response.photo_file_id) == ("cv-1", "ph-1")
    assert response.consent is True
    assert response.submitted_at == datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)


def _response(**fields) -> FormResponse:
    base = {
        "response_id": "r1",
        "full_name": "Nadia Karim",
        "email": "c5@example.com",
        "file_id": "cv-1",
        "file_name": "cv.pdf",
        "photo_file_id": "ph-1",
        "photo_file_name": "me.jpg",
        "consent": True,
        "submitted_at": NOW,
    }
    return FormResponse(**{**base, **fields})


@pytest.fixture()
def storage(monkeypatch, tmp_path):
    monkeypatch.setattr(get_settings(), "cv_storage_dir", str(tmp_path))
    monkeypatch.setattr(intake_service.google_drive, "download_file", lambda file_id, mb: b"x")
    return tmp_path


def test_without_consent_the_photo_is_not_even_read(storage, monkeypatch) -> None:
    monkeypatch.setattr(face_service, "check_photo", lambda content: pytest.fail("read"))

    face = intake_service.enrol_face(2, _response(consent=False))

    assert face == {"face_status": FaceStatus.NO_CONSENT}


def test_no_photo_is_recorded(storage) -> None:
    face = intake_service.enrol_face(2, _response(photo_file_id=""))

    assert face["face_status"] == FaceStatus.NO_PHOTO and face["face_consent_at"] == NOW


def test_an_unusable_photo_keeps_the_reason_and_stores_nothing(storage, monkeypatch) -> None:
    monkeypatch.setattr(
        face_service, "check_photo", lambda content: face_service.FaceCheck(problem="too_dark")
    )

    face = intake_service.enrol_face(2, _response())

    assert face["face_status"] == FaceStatus.PHOTO_UNUSABLE and face["face_problem"] == "too_dark"
    assert not any(storage.rglob("*.jpg"))


def test_a_good_photo_is_stored_under_a_random_name_with_its_code(storage, monkeypatch) -> None:
    image = np.full((400, 300, 3), 120, dtype=np.uint8)
    monkeypatch.setattr(
        face_service, "check_photo", lambda content: face_service.FaceCheck(code=INVITED, image=image)
    )

    face = intake_service.enrol_face(2, _response())

    path = Path(face["photo_path"])
    assert face["face_status"] == FaceStatus.ENROLLED and face["face_code"] == INVITED
    assert path.parent == storage / "2" / "photos" and path.suffix == ".jpg"
    assert "Nadia" not in path.name


def test_a_photo_of_the_wrong_type_is_not_downloaded(storage, monkeypatch) -> None:
    monkeypatch.setattr(
        intake_service.google_drive, "download_file", lambda *args: pytest.fail("downloaded")
    )

    face = intake_service.enrol_face(2, _response(photo_file_name="me.heic"))

    assert face["face_problem"] == face_service.NOT_AN_IMAGE


# --- Endpoints ---


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.db.session import get_db
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_db] = lambda: FakeDB(_session())
    return TestClient(app)


def _candidate_pass() -> dict:
    from app.core.security import create_access_token
    from app.models.enums import UserRole

    token = create_access_token("5", UserRole.CANDIDATE, timedelta(hours=1), session_id=9)
    return {"Authorization": f"Bearer {token}"}


def test_a_candidate_cannot_open_an_application_photo(client) -> None:
    response = client.get("/candidates/5/photo", headers=_candidate_pass())

    assert response.status_code == 403


def test_the_identity_photo_needs_a_candidate_pass(client) -> None:
    response = client.post("/join/identity", files={"photo": ("p.jpg", b"x", "image/jpeg")})

    assert response.status_code == 401


def test_the_pin_must_be_eight_digits(client) -> None:
    response = client.post("/join/pin", json={"token": TOKEN, "pin": "1234"})

    assert response.status_code == 422
    assert "1234" not in response.text
