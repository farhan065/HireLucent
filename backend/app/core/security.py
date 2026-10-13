"""Password hashing with Argon2 and signed access tokens (JWT)."""

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

from app.core.config import get_settings

JWT_ALGORITHM = "HS256"

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Return a salted Argon2 hash of the password."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return True if the password matches the stored hash."""
    try:
        return _hasher.verify(password_hash, password)
    except VerificationError:
        return False


def create_access_token(
    subject: str,
    role: str,
    expires_in: timedelta,
    session_id: int | None = None,
    link: str | None = None,
) -> str:
    """Create a signed token.

    subject is the user ID for an interviewer, or the candidate ID for a
    candidate. A candidate token also carries the one session it is valid for
    and a short fingerprint of its join link, so it stops working when the
    interview moves to a new link.
    """
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "exp": datetime.now(timezone.utc) + expires_in,
    }
    if session_id is not None:
        payload["session_id"] = session_id
    if link is not None:
        payload["link"] = link
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Return the token's contents, or None if it is invalid or expired."""
    try:
        return jwt.decode(
            token, get_settings().jwt_secret, algorithms=[JWT_ALGORITHM]
        )
    except jwt.InvalidTokenError:
        return None