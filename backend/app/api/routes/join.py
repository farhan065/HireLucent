"""The candidate's private interview link. No account is needed: the link
itself proves who the candidate is. Joining gives a pass for this one
interview, used while the candidate waits."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import Principal, require_candidate
from app.db.session import get_db
from app.schemas.error import ErrorResponse
from app.schemas.join import EnterRequest, JoinPass, LinkInfo, LinkRequest, WaitingStatus
from app.services import join_service

router = APIRouter(prefix="/join", tags=["Candidate join"])

LINK_GONE = {404: {"model": ErrorResponse, "description": "The link no longer works"}}


@router.post("/info", response_model=LinkInfo, summary="Read an interview link", responses=LINK_GONE)
def read_link(payload: LinkRequest, db: Session = Depends(get_db)) -> dict:
    """The job, the time and whether Join is open. Unknown, moved, cancelled
    and ended links all answer 404."""
    return join_service.link_info(db, payload.token)


@router.post(
    "/enter",
    response_model=JoinPass,
    summary="Join the waiting room",
    responses={
        **LINK_GONE,
        409: {"model": ErrorResponse, "description": "Join is not open yet"},
    },
)
def enter_waiting_room(payload: EnterRequest, db: Session = Depends(get_db)) -> JoinPass:
    """Saves the candidate's consent and puts them in the waiting room."""
    return JoinPass(access_token=join_service.enter(db, payload.token))


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
