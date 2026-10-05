"""AI status endpoint."""

from fastapi import APIRouter, Depends

from app.ai import client
from app.api.deps import require_interviewer
from app.core.config import Settings, get_settings
from app.core.errors import ServiceUnavailableError
from app.schemas.ai import AIModelStatus, AIStatusResponse

router = APIRouter(
    prefix="/ai", tags=["AI"], dependencies=[Depends(require_interviewer)]
)


def _check(call) -> str:
    """Return "ok" if the AI call works, otherwise "unavailable"."""
    try:
        call()
    except ServiceUnavailableError:
        return "unavailable"
    return "ok"


@router.get(
    "/status",
    response_model=AIStatusResponse,
    summary="Check that the AI models can be reached",
)
def read_ai_status(settings: Settings = Depends(get_settings)) -> AIStatusResponse:
    """Make one small call to the chat model and one to the embedding model."""
    return AIStatusResponse(
        llm=AIModelStatus(
            provider=settings.llm_provider,
            model=settings.llm_model,
            status=_check(lambda: client.generate_text("Reply with the word: ok")),
        ),
        embeddings=AIModelStatus(
            provider=settings.embedding_provider,
            model=settings.embedding_model,
            status=_check(lambda: client.embed_query("status check")),
        ),
    )