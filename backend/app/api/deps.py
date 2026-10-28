"""Shared endpoint dependencies: who is calling, and are they allowed."""

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.models.enums import UserRole

# auto_error=False so a missing token uses our uniform error response.
bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    """The caller, as described by a valid access token."""

    subject_id: int
    role: str
    session_id: int | None = None
    link: str | None = None


def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Principal:
    """Read and check the bearer token. Raises 401 if missing or invalid."""
    if credentials is None:
        raise UnauthorizedError("Sign in to continue.")

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise UnauthorizedError("Your session has expired. Please sign in again.")

    return Principal(
        subject_id=int(payload["sub"]),
        role=payload["role"],
        session_id=payload.get("session_id"),
        link=payload.get("link"),
    )


def require_role(role: UserRole) -> Callable[[Principal], Principal]:
    """Build a dependency that allows only callers with the given role."""

    def check_role(
        principal: Principal = Depends(get_current_principal),
    ) -> Principal:
        if principal.role != role:
            raise ForbiddenError("You do not have access to this.")
        return principal

    return check_role


require_interviewer = require_role(UserRole.INTERVIEWER)
require_candidate = require_role(UserRole.CANDIDATE)