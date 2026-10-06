"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    """Typed application settings.

    Values come from environment variables. For local runs outside Docker,
    they are also read from a .env file in the backend folder or repo root.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "HireLucent API"
    app_version: str = "0.1.0"
    app_env: Literal["development", "test", "production"] = "development"

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_service_name: str = "backend"
    log_dir: str = "logs"
    log_file_name: str = "hirelucent.log"
    log_file_max_bytes: int = 5_000_000
    log_file_backup_count: int = 5

    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    # AI models. The provider and model are chosen here, not in the code.
    llm_provider: Literal["gemini", "openai"] = "gemini"
    llm_model: str
    embedding_provider: Literal["ollama", "openai"] = "ollama"
    embedding_model: str
    ollama_base_url: str = "http://ollama:11434"
    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    ai_timeout_seconds: int = 60
    ai_max_attempts: int = 3
    # The provider's limit for your model. Calls are paced to stay under it.
    llm_requests_per_minute: int = Field(default=15, ge=1)

    # Vector database for the Knowledge Base and CV matching.
    chroma_host: str = "chromadb"
    chroma_port: int = 8000
    max_upload_mb: int = Field(default=10, ge=1)

    jwt_secret: str = Field(min_length=32)
    jwt_expire_minutes: int = 60

    # First interviewer account, created by the seed script if it is missing.
    seed_interviewer_email: str | None = None
    seed_interviewer_password: str | None = None
    seed_interviewer_name: str = "Interviewer"

    @property
    def database_url(self) -> URL:
        """Connection URL for PostgreSQL, built from the separate settings."""
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )

    @property
    def postgres_dsn(self) -> str:
        """The same connection as a plain PostgreSQL address, for LangGraph."""
        return self.database_url.set(drivername="postgresql").render_as_string(
            hide_password=False
        )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
