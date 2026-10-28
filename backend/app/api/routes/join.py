"""The candidate's private interview link. No account is needed: the link
itself proves who the candidate is. Joining gives a pass for this one
interview, used while the candidate waits."""

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_candidate
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.schemas.error import ErrorResponse
from app.schemas.join import (
    EnterRequest,
    IdentityAnswer,
    IdentitySkip,
    JoinPass,
    LinkInfo,
    LinkRequest,
    PinRequest,
    PinResult,
    WaitingStatus,
)
from app.schemas.video import RoomTokenResponse
from app.services import join_service

router = APIRouter(prefix="/join", tags=["Candidate join"])

LINK_GONE = {404: {"model": ErrorResponse, "description": "The link no longer works"}}


@router.post("/info", response_model=LinkInfo, summary="Read an interview link", responses=LINK_GONE)
def read_link(payload: LinkRequest, db: Session = Depends(get_db)) -> dict:
    """The job, the time and whether Join is open. Unknown, moved, cancelled
    and ended links all answer 404."""
    return join_service.link_info(db, payload.token)


@router.post(
    "/pin",
    response_model=PinResult,
    summary="Check the interview PIN",
    responses=LINK_GONE,
)
def check_pin(payload: PinRequest, db: Session = Depends(get_db)) -> PinResult:
    """The 8-digit PIN from the calendar invitation. Five wrong tries lock
    the link for 15 minutes."""
    result = join_service.check_pin(db, payload.token, payload.pin)
    return PinResult(
        result=result.result, tries_left=result.tries_left, locked_until=result.locked_until
    )


@router.post(
    "/enter",
    response_model=JoinPass,
    summary="Join the waiting room",
    responses={
        **LINK_GONE,
        401: {"model": ErrorResponse, "description": "Wrong PIN"},
        409: {"model": ErrorResponse, "description": "Join is not open yet, or the link is locked"},
    },
)
def enter_waiting_room(payload: EnterRequest, db: Session = Depends(get_db)) -> JoinPass:
    """Saves the candidate's consent and puts them in the waiting room. Says
    whether the identity photo is still to be taken."""
    access_token = join_service.enter(db, payload.token, pin=payload.pin)
    return JoinPass(
        access_token=access_token, photo_needed=join_service.needs_photo(db, payload.token)
    )


class PhotoTooLargeError(AppError):
    code = "photo_too_large"


PHOTO_TYPES = {"image/jpeg", "image/png"}


@router.post(
    "/identity",
    response_model=IdentityAnswer,
    summary="Send the identity photo",
    responses=LINK_GONE,
)
def send_identity_photo(
    photo: UploadFile = File(description="One JPEG or PNG photo from the camera."),
    principal: Principal = Depends(require_candidate),
    db: Session = Depends(get_db),
) -> IdentityAnswer:
    """Compared with the application photos of this job, then thrown away;
    it is never stored. The candidate is told only "done" or "try again"."""
    max_bytes = get_settings().max_photo_mb * 1024 * 1024
    if photo.content_type not in PHOTO_TYPES:
        raise AppError("The photo must be a JPEG or PNG image.")
    content = photo.file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise PhotoTooLargeError("The photo is too large.")
    state, tries_left = join_service.identity_photo(
        db, principal.session_id, principal.link, content
    )
    return IdentityAnswer(state=state, tries_left=tries_left)


@router.post(
    "/identity/skip",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Join without the identity photo",
    responses=LINK_GONE,
)
def skip_identity_photo(
    payload: IdentitySkip,
    principal: Principal = Depends(require_candidate),
    db: Session = Depends(get_db),
) -> None:
    """For a candidate with no camera, or after three unusable photos. The
    interviewer sees "Identity not checked" with the reason."""
    join_service.skip_identity(db, principal.session_id, principal.link, payload.reason)


@router.get(
    "/status",
    response_model=WaitingStatus,
    summary="Check in from the waiting room",
)
def check_in(
    principal: Principal = Depends(require_candidate), db: Session = Depends(get_db)
) -> WaitingStatus:
    """Called every few seconds while the candidate waits. Says whether
    they are still waiting, the interview has started, or it has ended."""
    state = join_service.check_in(db, principal.session_id, principal.link)
    return WaitingStatus(state=state)


@router.post(
    "/leave",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Leave the waiting room",
)
def leave_waiting_room(
    principal: Principal = Depends(require_candidate), db: Session = Depends(get_db)
) -> None:
    join_service.leave(db, principal.session_id, principal.link)


@router.post(
    "/room",
    response_model=RoomTokenResponse,
    summary="Join the interview room",
    responses={409: {"model": ErrorResponse, "description": "Not admitted yet"}},
)
def join_room(
    principal: Principal = Depends(require_candidate), db: Session = Depends(get_db)
) -> dict:
    """The candidate's pass for the video room, given only after the
    interviewer let them in."""
    return join_service.room_pass(db, principal.session_id, principal.link)
