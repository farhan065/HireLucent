"""Builds the chat model and the embedding model chosen in the settings.

Switching provider (for example Gemini to OpenAI) is a change to .env only.
"""

from functools import lru_cache

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import OllamaEmbeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.core.config import get_settings


def build_rate_limiter(requests_per_minute: int) -> InMemoryRateLimiter:
    """Pace model calls so they stay under the provider's per-minute limit.

    Each call waits its turn before it is sent. With a bucket size of one, no
    burst is allowed, so the limit cannot be exceeded.
    """
    return InMemoryRateLimiter(
        requests_per_second=requests_per_minute / 60,
        check_every_n_seconds=0.1,
        max_bucket_size=1,
    )


@lru_cache
def get_chat_model() -> BaseChatModel:
    """Return the configured chat model.

    temperature=0 keeps answers as repeatable as possible, which matters for
    stable candidate scores. Retries are handled in app.ai.client, so the
    provider's own retries are switched off.
    """
    settings = get_settings()
    options = {
        "model": settings.llm_model,
        "temperature": 0,
        "timeout": settings.ai_timeout_seconds,
        "max_retries": 0,
        "rate_limiter": build_rate_limiter(settings.llm_requests_per_minute),
    }
    if settings.llm_provider == "openai":
        return ChatOpenAI(api_key=settings.openai_api_key, **options)
    return ChatGoogleGenerativeAI(google_api_key=settings.gemini_api_key, **options)


@lru_cache
def get_embedding_model() -> Embeddings:
    """Return the configured embedding model."""
    settings = get_settings()
    if settings.embedding_provider == "openai":
        return OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.openai_api_key,
            timeout=settings.ai_timeout_seconds,
            max_retries=0,
        )
    return OllamaEmbeddings(
        model=settings.embedding_model,
        base_url=settings.ollama_base_url,
        client_kwargs={"timeout": settings.ai_timeout_seconds},
    )
