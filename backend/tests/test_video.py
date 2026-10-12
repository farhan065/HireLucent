"""Tests for the video room tokens and the temporary test endpoint."""

from datetime import timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import create_access_token
from app.main import create_app
from app.models.enums import UserRole

LIVEKIT_SECRET = "s" * 32


@pytest.fixture()
def livekit_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "livekit_api_key", "devkey")
    monkeypatch.setattr(settings, "livekit_api_secret", LIVEKIT_SECRET)


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


def _auth(role: UserRole) -> dict[str, str]:
    token = create_access_token(subject="1", role=role, expires_in=timedelta(minutes=5))
    return {"Authorization": f"Bearer {token}"}


def _read_room_token(token: str) -> dict:
    return jwt.decode(token, LIVEKIT_SECRET, algorithms=["HS256"])


@pytest.mark.usefixtures("livekit_keys")
def test_interviewer_gets_a_token_for_the_test_room(client: TestClient) -> None:
    response = client.post("/video/test-token", headers=_auth(UserRole.INTERVIEWER))

    assert response.status_code == 200
    body = response.json()
    assert body["room"] == "livekit-test"
    claims = _read_room_token(body["token"])
    assert claims["sub"] == body["identity"]
    assert claims["video"]["room"] == "livekit-test"
    assert claims["video"]["roomJoin"] is True
    assert claims["video"]["canPublish"] is True


@pytest.mark.usefixtures("livekit_keys")
def test_two_tabs_get_different_participant_names(client: TestClient) -> None:
    first = client.post("/video/test-token", headers=_auth(UserRole.INTERVIEWER))
    second = client.post("/video/test-token", headers=_auth(UserRole.INTERVIEWER))

    assert first.json()["identity"] != second.json()["identity"]


@pytest.mark.usefixtures("livekit_keys")
def test_candidate_and_anonymous_callers_are_refused(client: TestClient) -> None:
    assert client.post("/video/test-token").status_code == 401
    candidate = client.post("/video/test-token", headers=_auth(UserRole.CANDIDATE))
    assert candidate.status_code == 403


def test_missing_livekit_keys_give_a_clear_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "livekit_api_key", "")

    response = client.post("/video/test-token", headers=_auth(UserRole.INTERVIEWER))

    assert response.status_code == 503
    assert "LiveKit" in response.json()["error"]["message"]
