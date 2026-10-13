"""Tests for the interview rooms: room passes, opening the room, admitting
the candidate, ending the interview and the candidate's room pass."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.errors import ConflictError, ServiceUnavailableError
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import create_app
from app.models import Candidate, InterviewSession
from app.models.enums import CandidateStatus, SessionStatus, UserRole
from app.services import join_service, room_service, session_service, video

LIVEKIT_SECRET = "s" * 32
NOW = datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)
TOKEN_HASH = session_service.hash_token("a-private-token-for-the-tests")


@pytest.fixture(autouse=True)
def livekit(monkeypatch: pytest.MonkeyPatch) -> list:
    """LiveKit keys for signing, and closed rooms recorded instead of sent."""
    settings = get_settings()
    monkeypatch.setattr(settings, "livekit_api_key", "devkey")
    monkeypatch.setattr(settings, "livekit_api_secret", LIVEKIT_SECRET)
    closed = []
    monkeypatch.setattr(video, "close_room", lambda room: closed.append(room) or True)
    return closed


class FakeDB:
    def __init__(self, session):
        self.session = session
        self.commits = 0

    def get(self, model, key):
        return self.session if key == self.session.id else None

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
        id=5, job_id=2, full_name="Nadia Karim", status=CandidateStatus.INTERVIEW_SCHEDULED
    )
    return session


def _claims(token: str) -> dict:
    return jwt.decode(token, LIVEKIT_SECRET, algorithms=["HS256"])


# --- Room passes ---


def test_a_room_pass_is_for_one_room_and_can_send_and_receive() -> None:
    claims = _claims(video.create_room_token("interview-9", "candidate", "Nadia", timedelta(hours=1)))

    assert claims["sub"] == "candidate"
    assert claims["video"]["room"] == "interview-9"
    assert claims["video"]["roomJoin"] is True
    assert claims["video"]["canPublish"] is True and claims["video"]["canSubscribe"] is True


def test_missing_livekit_keys_give_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "livekit_api_key", "")

    with pytest.raises(ServiceUnavailableError, match="LiveKit"):
        video.create_room_token("interview-9", "candidate", "Nadia", timedelta(hours=1))


# --- Opening the room ---


def test_the_interviewer_opens_the_room_when_join_opens() -> None:
    session = _session()

    room = room_service.open_room(FakeDB(session), 9, now=NOW)

    assert room["room"] == "interview-9" and room["identity"] == "interviewer"
    assert _claims(room["token"])["video"]["room"] == "interview-9"
    assert session.interviewer_joined_at == NOW


@pytest.mark.parametrize(
    ("session", "message"),
    [
        (_session(start=NOW + timedelta(hours=3)), "opens 10 minutes before"),
        (_session(SessionStatus.COMPLETED), "has ended"),
        (_session(SessionStatus.CANCELLED), "has ended"),
    ],
)
def test_the_room_is_closed_too_early_or_after_the_end(session, message: str) -> None:
    with pytest.raises(ConflictError, match=message):
        room_service.open_room(FakeDB(session), 9, now=NOW)


# --- Admitting the candidate ---


def test_admitting_the_waiting_candidate_starts_the_interview() -> None:
    session = _session()
    session.candidate_seen_at = datetime.now(timezone.utc)

    room_service.admit(FakeDB(session), 9, now=NOW)

    assert session.status == SessionStatus.IN_PROGRESS and session.started_at == NOW


def test_nobody_can_be_admitted_who_is_not_waiting() -> None:
    session = _session()

    with pytest.raises(ConflictError, match="not in the waiting room"):
        room_service.admit(FakeDB(session), 9, now=NOW)
    assert session.status == SessionStatus.SCHEDULED


# --- The candidate's room pass ---


def test_the_candidate_gets_a_room_pass_only_after_being_admitted() -> None:
    fingerprint = TOKEN_HASH[: join_service.FINGERPRINT_LENGTH]
    waiting = _session()

    with pytest.raises(ConflictError, match="not started"):
        join_service.room_pass(FakeDB(waiting), 9, fingerprint)

    started = _session(SessionStatus.IN_PROGRESS)
    room = join_service.room_pass(FakeDB(started), 9, fingerprint)
    assert room["identity"] == "candidate"
    assert _claims(room["token"])["name"] == "Nadia"


# --- Ending ---


def test_ending_completes_the_interview_and_closes_its_room(livekit: list) -> None:
    session = _session(SessionStatus.IN_PROGRESS)

    room_service.end(FakeDB(session), 9, now=NOW)

    assert session.status == SessionStatus.COMPLETED and session.ended_at == NOW
    assert livekit == ["interview-9"]


def test_an_interview_that_has_not_started_cannot_be_ended() -> None:
    with pytest.raises(ConflictError, match="not started"):
        room_service.end(FakeDB(_session()), 9, now=NOW)


# --- Who may do what ---


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: FakeDB(_session())
    return TestClient(app)


def _auth(role: UserRole) -> dict[str, str]:
    token = create_access_token(subject="1", role=role, expires_in=timedelta(minutes=5))
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("action", ["room", "admit", "end"])
def test_only_the_interviewer_controls_the_room(client: TestClient, action: str) -> None:
    assert client.post(f"/interviews/9/{action}").status_code == 401
    response = client.post(f"/interviews/9/{action}", headers=_auth(UserRole.CANDIDATE))
    assert response.status_code == 403


def test_the_test_room_is_gone(client: TestClient) -> None:
    response = client.post("/video/test-token", headers=_auth(UserRole.INTERVIEWER))

    assert response.status_code == 404
