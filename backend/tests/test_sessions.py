"""Tests for interview sessions: times, join links, lifecycle rules and the
interviews list."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import create_app
from app.models import Candidate, InterviewSession
from app.models.enums import CandidateStatus, SessionStatus, UserRole
from app.services import session_service
from app.services.session_service import JoinState

NOW = datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)
START = NOW + timedelta(hours=2)
END = START + timedelta(minutes=45)


class FakeDB:
    """Just enough of a database session for the service's rules.

    `counts` are the answers to the service's count queries, in order.
    """

    def __init__(self, objects=None, counts=()):
        self.objects = objects or {}
        self.counts = list(counts)
        self.added = []
        self.commits = 0

    def get(self, model, key):
        return self.objects.get((model, key))

    def scalar(self, _query):
        return self.counts.pop(0)

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.commits += 1


def _candidate(status=CandidateStatus.SHORTLISTED) -> Candidate:
    return Candidate(id=5, job_id=2, full_name="Test Candidate", status=status)


def _session(status=SessionStatus.SCHEDULED, start=START, end=END) -> InterviewSession:
    session = InterviewSession(
        id=9,
        candidate_id=5,
        job_id=2,
        created_by=1,
        scheduled_start=start,
        scheduled_end=end,
        join_token_hash="old-hash",
        status=status,
    )
    session.candidate = _candidate(CandidateStatus.INTERVIEW_SCHEDULED)
    return session


# --- Join tokens ---


def test_token_is_random_and_only_its_hash_is_kept() -> None:
    token, token_hash = session_service.new_join_token()
    other, _ = session_service.new_join_token()

    assert len(token) >= 43
    assert token != other
    assert token_hash != token
    assert session_service.hash_token(token) == token_hash


# --- Times ---


def test_valid_times_are_accepted() -> None:
    session_service.check_times(START, END, NOW)


@pytest.mark.parametrize(
    ("start", "end", "message"),
    [
        (NOW + timedelta(minutes=10), NOW + timedelta(minutes=55), "15 minutes from now"),
        (NOW + timedelta(days=61), NOW + timedelta(days=61, minutes=45), "60 days"),
        (START, START + timedelta(minutes=10), "between 15 and 120"),
        (START, START + timedelta(minutes=121), "between 15 and 120"),
        (START.replace(tzinfo=None), END.replace(tzinfo=None), "time zone"),
    ],
)
def test_impossible_times_are_refused(start, end, message: str) -> None:
    with pytest.raises(AppError, match=message):
        session_service.check_times(start, end, NOW)


# --- Join window ---


@pytest.mark.parametrize(
    ("status", "now", "expected"),
    [
        (SessionStatus.SCHEDULED, START - timedelta(minutes=11), JoinState.TOO_EARLY),
        (SessionStatus.SCHEDULED, START - timedelta(minutes=10), JoinState.OPEN),
        (SessionStatus.SCHEDULED, END, JoinState.OPEN),
        (SessionStatus.SCHEDULED, END + timedelta(minutes=1), JoinState.MISSED),
        (SessionStatus.IN_PROGRESS, END + timedelta(minutes=20), JoinState.OPEN),
        (SessionStatus.COMPLETED, START, JoinState.ENDED),
        (SessionStatus.CANCELLED, START, JoinState.ENDED),
    ],
)
def test_join_state(status, now, expected) -> None:
    assert session_service.join_state(_session(status), now) == expected


# --- Scheduling ---


def test_shortlisted_candidate_is_scheduled() -> None:
    candidate = _candidate()
    db = FakeDB({(Candidate, 5): candidate}, counts=[0, 0])

    session, token = session_service.create_session(db, 5, START, END, created_by=1, now=NOW)

    assert db.added == [session] and db.commits == 1
    assert session.job_id == 2 and session.created_by == 1
    assert session.status == SessionStatus.SCHEDULED
    assert session.join_token_hash == session_service.hash_token(token)
    assert candidate.status == CandidateStatus.INTERVIEW_SCHEDULED


def test_missing_candidate_gives_404() -> None:
    with pytest.raises(NotFoundError):
        session_service.create_session(FakeDB(), 5, START, END, created_by=1, now=NOW)


@pytest.mark.parametrize(
    ("status", "counts", "message"),
    [
        (CandidateStatus.SCREENED, [], "Only shortlisted"),
        (CandidateStatus.SHORTLISTED, [1], "already has an upcoming interview"),
        (CandidateStatus.SHORTLISTED, [0, 1], "already have an interview at that time"),
    ],
)
def test_scheduling_is_refused(status, counts, message: str) -> None:
    db = FakeDB({(Candidate, 5): _candidate(status)}, counts=counts)

    with pytest.raises(ConflictError, match=message):
        session_service.create_session(db, 5, START, END, created_by=1, now=NOW)
    assert db.added == [] and db.commits == 0


def test_reschedule_gives_a_new_link() -> None:
    session = _session()
    session.candidate_joined_at = NOW
    later = START + timedelta(days=1)
    db = FakeDB({(InterviewSession, 9): session}, counts=[0])

    _, token = session_service.reschedule(db, 9, later, later + timedelta(hours=1), now=NOW)

    assert session.scheduled_start == later
    assert session.join_token_hash == session_service.hash_token(token)
    assert session.join_token_hash != "old-hash"
    assert session.candidate_joined_at is None


@pytest.mark.parametrize("action", ["reschedule", "cancel"])
def test_started_interview_cannot_be_moved_or_cancelled(action: str) -> None:
    db = FakeDB({(InterviewSession, 9): _session(SessionStatus.IN_PROGRESS)})

    with pytest.raises(ConflictError, match="not started"):
        if action == "cancel":
            session_service.cancel(db, 9, now=NOW)
        else:
            session_service.reschedule(db, 9, START, END, now=NOW)


def test_cancel_puts_the_candidate_back_on_the_shortlist() -> None:
    session = _session()
    db = FakeDB({(InterviewSession, 9): session}, counts=[0])

    session_service.cancel(db, 9, now=NOW)

    assert session.status == SessionStatus.CANCELLED
    assert session.cancelled_at == NOW
    assert session.candidate.status == CandidateStatus.SHORTLISTED


def test_cancel_keeps_status_after_an_earlier_interview() -> None:
    session = _session()
    db = FakeDB({(InterviewSession, 9): session}, counts=[1])

    session_service.cancel(db, 9, now=NOW)

    assert session.candidate.status == CandidateStatus.INTERVIEW_SCHEDULED


# --- Requirement edits ---


def test_rules_are_locked_once_a_job_has_interviews() -> None:
    with pytest.raises(ConflictError, match="cannot change"):
        session_service.ensure_rules_can_change(FakeDB(counts=[2]), job_id=2)


def test_rules_can_change_without_interviews() -> None:
    session_service.ensure_rules_can_change(FakeDB(counts=[0]), job_id=2)


# --- Interviews list endpoint ---


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    row = SimpleNamespace(
        id=9,
        candidate_id=5,
        candidate_name="Test Candidate",
        scheduled_start=START,
        scheduled_end=END,
        status="scheduled",
        join_token_hash="must-not-be-sent",
        candidate_joined_at=None,
        interviewer_joined_at=None,
        started_at=None,
        ended_at=None,
        cancelled_at=None,
    )
    monkeypatch.setattr(session_service, "list_for_job", lambda db, job_id: [row])
    app = create_app()
    app.dependency_overrides[get_db] = lambda: None
    return TestClient(app)


def _auth(role: UserRole) -> dict[str, str]:
    token = create_access_token(subject="1", role=role, expires_in=timedelta(minutes=5))
    return {"Authorization": f"Bearer {token}"}


def test_interviewer_sees_the_interviews_without_tokens(client: TestClient) -> None:
    response = client.get("/jobs/2/interviews", headers=_auth(UserRole.INTERVIEWER))

    assert response.status_code == 200
    [item] = response.json()
    assert item["candidate_name"] == "Test Candidate"
    assert item["status"] == "scheduled"
    assert "join_token_hash" not in item and "must-not-be-sent" not in response.text


def test_candidate_cannot_list_interviews(client: TestClient) -> None:
    response = client.get("/jobs/2/interviews", headers=_auth(UserRole.CANDIDATE))

    assert response.status_code == 403
