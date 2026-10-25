"""Access separation in one place (BID N9, role separation): every route of
the API is called with a candidate's pass, with an interviewer's token and
with no token at all.

- Interviewer routes (everything except the few public ones and /join)
  refuse a candidate (403) and anyone without a token (401), so a candidate
  can never reach scores, rankings, reports, transcripts or emails.
- Candidate routes behind the pass (/join/identity, /join/status, ...)
  refuse an interviewer's token (403) and no token (401).

The routes are read from the app itself, so a route added later is checked
too. Nothing reaches the database: every request stops at the access check.
"""

import re
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import create_app
from app.models.enums import UserRole

# Open to everyone: health, sign-in, and the three join steps that come
# before the candidate has a pass (the join link and PIN are checked inside).
PUBLIC = {
    ("GET", "/health"),
    ("POST", "/auth/login"),
    ("POST", "/join/info"),
    ("POST", "/join/pin"),
    ("POST", "/join/enter"),
}
CANDIDATE_PREFIX = "/join/"


def _routes() -> list[tuple[str, str]]:
    paths = create_app().openapi()["paths"]
    return sorted(
        (method.upper(), path)
        for path, operations in paths.items()
        for method in operations
        if method in {"get", "post", "put", "patch", "delete"}
    )


ROUTES = _routes()
INTERVIEWER_ROUTES = [
    route
    for route in ROUTES
    if route not in PUBLIC and not route[1].startswith(CANDIDATE_PREFIX)
]
CANDIDATE_ROUTES = [
    route for route in ROUTES if route not in PUBLIC and route[1].startswith(CANDIDATE_PREFIX)
]


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=False)


def _url(path: str) -> str:
    """Fill each path parameter with 1."""
    return re.sub(r"\{[^}]+\}", "1", path)


def _token(role: UserRole) -> dict:
    token = create_access_token(
        subject="1",
        role=role,
        expires_in=timedelta(minutes=5),
        session_id=1 if role == UserRole.CANDIDATE else None,
        link="abc" if role == UserRole.CANDIDATE else None,
    )
    return {"Authorization": f"Bearer {token}"}


def test_the_route_list_covers_the_api() -> None:
    # A guard against reading the routes wrongly and checking nothing.
    assert len(INTERVIEWER_ROUTES) > 60
    assert ("GET", "/interviews/{session_id}/assessment") in INTERVIEWER_ROUTES
    assert ("GET", "/interviews/{session_id}/transcript") in INTERVIEWER_ROUTES
    assert ("GET", "/jobs/{job_id}/assessments") in INTERVIEWER_ROUTES
    assert ("GET", "/join/status") in CANDIDATE_ROUTES


@pytest.mark.parametrize(("method", "path"), INTERVIEWER_ROUTES)
def test_a_candidate_cannot_reach_interviewer_routes(client, method, path) -> None:
    response = client.request(method, _url(path), headers=_token(UserRole.CANDIDATE))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.parametrize(("method", "path"), INTERVIEWER_ROUTES)
def test_interviewer_routes_need_a_token(client, method, path) -> None:
    response = client.request(method, _url(path))

    assert response.status_code == 401


@pytest.mark.parametrize(("method", "path"), CANDIDATE_ROUTES)
def test_an_interviewer_cannot_use_the_candidate_pass_routes(client, method, path) -> None:
    response = client.request(method, _url(path), headers=_token(UserRole.INTERVIEWER))

    assert response.status_code == 403


@pytest.mark.parametrize(("method", "path"), CANDIDATE_ROUTES)
def test_candidate_pass_routes_need_a_token(client, method, path) -> None:
    response = client.request(method, _url(path))

    assert response.status_code == 401
