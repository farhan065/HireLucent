"""Authentication endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_interviewer
from app.core.errors import UnauthorizedError
from app.db.session import get_db
from app.models import User
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.schemas.error import ErrorResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Sign in as an interviewer",
    responses={401: {"model": ErrorResponse, "description": "Wrong credentials"}},
)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Check the email and password and return an access token."""
    return auth_service.login(db, payload.email, payload.password)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the signed-in interviewer",
    responses={
        401: {"model": ErrorResponse, "description": "Not signed in"},
        403: {"model": ErrorResponse, "description": "Not an interviewer"},
    },
)
def read_current_user(
    principal: Principal = Depends(require_interviewer),
    db: Session = Depends(get_db),
) -> User:
    """Return the account that the access token belongs to."""
    user = db.get(User, principal.subject_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Your session has expired. Please sign in again.")
    return user