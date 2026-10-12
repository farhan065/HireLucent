"""Video test endpoint.

Temporary: it lets two browser tabs check that the LiveKit server works.
It is removed when the interview room is built.
"""

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends

from app.api.deps import Principal, require_interviewer
from app.core.config import get_settings
from app.core.logging import get_logger, log_event
from app.schemas.error import ErrorResponse
from app.schemas.video import RoomTokenResponse
from app.services import video

logger = get_logger(__name__)

router = APIRouter(prefix="/video", tags=["Video"])

TEST_ROOM = "livekit-test"


@router.post(
    "/test-token",
    response_model=RoomTokenResponse,
    summary="Join the video test room (temporary)",
    responses={503: {"model": ErrorResponse, "description": "Video is not set up"}},
)
def create_test_token(
    principal: Principal = Depends(require_interviewer),
) -> RoomTokenResponse:
    """Each call gets its own participant name, so two tabs signed in as
    the same interviewer can join the room together."""
    identity = f"interviewer-{principal.subject_id}-{secrets.token_hex(3)}"
    token = video.create_room_token(
        room=TEST_ROOM,
        identity=identity,
        name=f"Tab {identity[-6:]}",
        valid_for=timedelta(hours=1),
    )
    log_event(logger, "video_test_token_issued", user_id=principal.subject_id)
    return RoomTokenResponse(
        url=get_settings().livekit_url, room=TEST_ROOM, identity=identity, token=token
    )
