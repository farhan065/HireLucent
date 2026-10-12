"""Tests for the candidate's private interview link: reading it, joining the
waiting room with consent, checking in and leaving."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.errors import ConflictError, NotFoundError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.main import create_app
from app.models import Candidate, InterviewSession, Job
from app.models.enums import CandidateStatus, SessionStatus, UserRole
from app.services import join_service, session_service

NOW = datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)
TOKEN, TOKEN_HASH = "a-private-token-for-the-tests", session_service.hash_token(
    "a-private-token-for-the-tests"
)


class FakeDB:
    def __init__(self, session):
        self.session = session
        self.commits = 0

    def scalar(self, _query):
        return self.session

    def get(self, model, key):
        if model is Job:
            return Job(id=2, title="Backend Engineer")
        return self.session if self.session and key == self.session.id else None

    def commit(self):
        self.commits += 1


def _session(status=SessionStatus.SCHEDULED, start=NOW + timedelta(minutes=5)) -> InterviewSession:
    session = InterviewSession(
        id=9,
        candidate_id=5,
        job_id=2,
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=45),
        join_token_hash=TOKEN_HASH,
        status=status,
    )
    session.candidate = Candidate(
        id=5,
        job_id=2,
        full_name="Nadia Karim",
        email="candidate@example.com",
        status=CandidateStatus.INTERVIEW_SCHEDULED,
    )
    return session


FINGERPRINT = TOKEN_HASH[: join_service.FINGERPRINT_LENGTH]


# --- Reading the link ---


def test_link_shows_first_name_job_and_times_but_no_email() -> None:
    info = join_service.link_info(FakeDB(_session()), TOKEN, now=NOW)

    assert info["state"] == "open"
    assert info["first_name"] == "Nadia"
    assert info["job_title"] == "Backend Engineer"
    assert info["length_minutes"] == 45
    assert "candidate@example.com" not in str(info)


@pytest.mark.parametrize(
    ("status", "start", "state"),
    [
        (SessionStatus.SCHEDULED, NOW + timedelta(hours=2), "too_early"),
        (SessionStatus.SCHEDULED, NOW - timedelta(hours=2), "ended"),
        (SessionStatus.CANCELLED, NOW + timedelta(minutes=5), "ended"),
        (SessionStatus.COMPLETED, NOW - timedelta(minutes=30), "ended"),
    ],
)
def test_link_state(status, start, state: str) -> None:
    info = join_service.link_info(FakeDB(_session(status, start)), TOKEN, now=NOW)

    assert info["state"] == state


def test_an_unknown_link_no_longer_works() -> None:
    with pytest.raises(NotFoundError, match="no longer works"):
        join_service.link_info(FakeDB(None), TOKEN, now=NOW)


# --- Joining the waiting room ---


def test_joining_saves_consent_and_gives_a_pass_for_this_interview() -> None:
    session = _session()
    db = FakeDB(session)

    token = join_service.enter(db, TOKEN, now=NOW)

    assert session.consent_given_at == NOW
    assert session.candidate_joined_at == NOW and session.candidate_seen_at == NOW
    payload = decode_access_token(token)
    assert payload["role"] == UserRole.CANDIDATE
    assert payload["session_id"] == 9 and payload["link"] == FINGERPRINT


def test_join_is_refused_before_it_opens() -> None:
    session = _session(start=NOW + timedelta(hours=2))

    with pytest.raises(ConflictError, match="cannot be joined yet"):
        join_service.enter(FakeDB(session), TOKEN, now=NOW)
    assert session.consent_given_at is None


def test_join_is_refused_after_the_interview_ended() -> None:
    with pytest.raises(NotFoundError):
        join_service.enter(FakeDB(_session(SessionStatus.CANCELLED)), TOKEN, now=NOW)


# --- Waiting ---


def test_checking_in_keeps_the_candidate_waiting() -> None:
    session = _session()

    state = join_service.check_in(FakeDB(session), 9, FINGERPRINT, now=NOW)

    assert state == "waiting" and session.candidate_seen_at == NOW


@pytest.mark.parametrize(
    ("status", "state"),
    [(SessionStatus.IN_PROGRESS, "started"), (SessionStatus.CANCELLED, "ended")],
)
def test_check_in_reports_a_started_or_ended_interview(status, state: str) -> None:
    assert join_service.check_in(FakeDB(_session(status)), 9, FINGERPRINT, now=NOW) == state


def test_a_pass_stops_working_when_the_interview_moves() -> None:
    session = _session()
    session.join_token_hash = "a-new-hash-after-rescheduling"

    with pytest.raises(UnauthorizedError):
        join_service.check_in(FakeDB(session), 9, FINGERPRINT, now=NOW)


def test_leaving_the_waiting_room() -> None:
    session = _session()
    session.candidate_seen_at = NOW

    join_service.leave(FakeDB(session), 9, FINGERPRINT)

    assert session.candidate_seen_at is None


def test_waiting_ends_without_a_recent_check_in() -> None:
    session = _session()
    now = datetime.now(timezone.utc)

    session.candidate_seen_at = now - timedelta(seconds=5)
    assert session.candidate_waiting is True
    session.candidate_seen_at = now - timedelta(seconds=30)
    assert session.candidate_waiting is False


# --- Endpoints ---


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: FakeDB(_session())
    return TestClient(app)


def test_info_endpoint_takes_the_token_in_the_body(client: TestClient) -> None:
    response = client.post("/join/info", json={"token": TOKEN})

    assert response.status_code == 200
    assert response.json()["first_name"] == "Nadia"


def test_join_needs_consent(client: TestClient) -> None:
    response = client.post("/join/enter", json={"token": TOKEN, "consent": False})

    assert response.status_code == 422


def test_status_needs_a_candidate_pass(client: TestClient) -> None:
    assert client.get("/join/status").status_code == 401
