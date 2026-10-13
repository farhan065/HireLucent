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
    # The interview room's AI Agent chat gives up sooner, so a slow AI
    # service never leaves the interviewer waiting for minutes.
    room_ai_timeout_seconds: int = Field(default=30, ge=5)
    room_ai_max_attempts: int = Field(default=2, ge=1)
    # The provider's limit for your model, minus a small safety margin.
    # Calls are paced to stay under it.
    llm_requests_per_minute: int = Field(default=14, ge=1)
    # CV screening may use only this many of those calls per minute, so the
    # rest stay free for the AI Agent and the interview room.
    llm_background_requests_per_minute: int = Field(default=10, ge=1)

    # Vector database for the Knowledge Base and CV matching.
    chroma_host: str = "chromadb"
    chroma_port: int = 8000
    max_upload_mb: int = Field(default=10, ge=1)
    # Where collected CVs are kept. A Docker volume, never the repository.
    cv_storage_dir: str = "/data/cv_intake"
    # CV screening: how many CVs are processed at once, and how many pages
    # of a scanned CV are read by OCR.
    screening_max_parallel: int = Field(default=4, ge=1)
    ocr_max_pages: int = Field(default=10, ge=1)

    # The RAG MCP server, which gives the assistant its search tools.
    mcp_rag_url: str = "http://mcp-rag:8001/mcp"
    mcp_rag_port: int = 8001
    # How close a stored job description must be to count as a reference.
    # Cosine distance: 0 is identical, 1 is unrelated.
    jd_reference_max_distance: float = Field(default=0.6, ge=0, le=2)
    # How close a question in the question bank must be to the topic asked.
    question_bank_max_distance: float = Field(default=0.6, ge=0, le=2)

    # The Blogger MCP server, which publishes approved job posts.
    mcp_blogger_url: str = "http://mcp-blogger:8002/mcp"
    blogger_blog_id: str = ""
    # The Google sign-in saved by scripts/google_auth.py.
    google_token_file: str = "/secrets/google_token.json"

    # The Google MCP server, which sends interview emails and calendar
    # invitations after the interviewer has approved them.
    mcp_google_url: str = "http://mcp-google:8003/mcp"
    mcp_google_port: int = 8003
    # How interview emails are signed. The address is the Gmail account you
    # signed in with; leave it empty to let Gmail fill it in.
    email_sender_name: str = "HireLucent Careers"
    email_sender_address: str = ""

    # LiveKit, the video server. The URL is the address the browser uses.
    # The key and secret sign room tokens and must match the livekit service.
    livekit_url: str = "ws://localhost:7880"
    # The same server as the backend reaches it, used to close a room when
    # an interview ends.
    livekit_api_url: str = "http://livekit:7880"
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    # The transcription worker runs inside the livekit service's network,
    # where the video server is localhost (the address it announces).
    capture_livekit_url: str = "ws://localhost:7880"
    # How often the worker looks for interviews that started or ended.
    capture_poll_seconds: float = Field(default=3, gt=0, le=60)
    # How many minutes before an interview's start the candidate can join.
    join_opens_minutes_before: int = Field(default=10, ge=0, le=60)
    # How far ahead an interview must be scheduled. Set it to 1 while testing
    # to send invitations and join almost at once.
    interview_min_notice_minutes: int = Field(default=15, ge=0, le=1440)
    # The time zone used in interview emails and for times typed to the AI
    # Agent. Times are stored in UTC; screens show the viewer's local time.
    app_timezone: str = "Asia/Dhaka"
    # The address of the web app, used to build candidates' join links.
    frontend_base_url: str = "http://localhost:3000"

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
