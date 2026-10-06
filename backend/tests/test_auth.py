"""Tests for access tokens and role separation."""

from datetime import timedelta

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from app.api.deps import Principal, require_candidate, require_interviewer
from app.core.security import create_access_token, decode_access_token
from app.main import create_app
from app.models.enums import UserRole


def _token(role: UserRole, minutes: int = 5, session_id: int | None = None) -> str:
    return create_access_token(
        subject="1",
        role=role,
        expires_in=timedelta(minutes=minutes),
        session_id=session_id,
    )


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def client() -> TestClient:
    app = create_app()

    @app.get("/_test/scores")
    def _scores(principal: Principal = Depends(require_interviewer)) -> dict:
        return {"subject_id": principal.subject_id}

    @app.get("/_test/room")
    def _room(principal: Principal = Depends(require_candidate)) -> dict:
        return {"session_id": principal.session_id}

    return TestClient(app)


def test_token_round_trip() -> None:
    payload = decode_access_token(_token(UserRole.CANDIDATE, session_id=7))

    assert payload is not None
    assert payload["sub"] == "1"
    assert payload["role"] == "candidate"
    assert payload["session_id"] == 7


def test_expired_and_tampered_tokens_are_invalid() -> None:
    assert decode_access_token(_token(UserRole.INTERVIEWER, minutes=-1)) is None
    assert decode_access_token(_token(UserRole.INTERVIEWER) + "x") is None


def test_interviewer_can_reach_interviewer_endpoint(client: TestClient) -> None:
    response = client.get("/_test/scores", headers=_auth(_token(UserRole.INTERVIEWER)))

    assert response.status_code == 200
    assert response.json() == {"subject_id": 1}


def test_candidate_gets_403_on_interviewer_endpoint(client: TestClient) -> None:
    response = client.get("/_test/scores", headers=_auth(_token(UserRole.CANDIDATE)))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_candidate_can_reach_candidate_endpoint(client: TestClient) -> None:
    token = _token(UserRole.CANDIDATE, session_id=7)

    response = client.get("/_test/room", headers=_auth(token))

    assert response.status_code == 200
    assert response.json() == {"session_id": 7}


def test_missing_token_gets_401(client: TestClient) -> None:
    response = client.get("/_test/scores")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_expired_token_gets_401(client: TestClient) -> None:
    token = _token(UserRole.INTERVIEWER, minutes=-1)

    response = client.get("/_test/scores", headers=_auth(token))

    assert response.status_code == 401