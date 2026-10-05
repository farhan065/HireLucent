"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Literal

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


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()