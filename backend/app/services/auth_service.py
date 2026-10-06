"""AuthService: checks interviewer credentials and issues access tokens."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import UnauthorizedError
from app.core.logging import get_logger, log_event
from app.core.security import create_access_token, verify_password
from app.models import User
from app.schemas.auth import TokenResponse

logger = get_logger(__name__)

# The same message for an unknown email and a wrong password, so the response
# does not reveal which emails have an account.
INVALID_CREDENTIALS = "Incorrect email or password."


def login(db: Session, email: str, password: str) -> TokenResponse:
    """Return an access token if the email and password are correct."""
    user = db.scalar(select(User).where(User.email == email))
    if (
        user is None
        or not user.is_active
        or not verify_password(password, user.password_hash)
    ):
        log_event(logger, "login_failed")
        raise UnauthorizedError(INVALID_CREDENTIALS)

    expires_in = timedelta(minutes=get_settings().jwt_expire_minutes)
    token = create_access_token(
        subject=str(user.id), role=user.role, expires_in=expires_in
    )
    log_event(logger, "login_succeeded", user_id=user.id)
    return TokenResponse(
        access_token=token, expires_in=int(expires_in.total_seconds())
    )