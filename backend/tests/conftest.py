"""Shared test setup."""

import pytest

from app.core.config import get_settings
from app.services import conversation_store


@pytest.fixture(autouse=True)
def default_interview_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    """The interview rules are set to their defaults, so testing values in
    your .env (such as a 1-minute notice) do not change the test results."""
    settings = get_settings()
    monkeypatch.setattr(settings, "interview_min_notice_minutes", 15)
    monkeypatch.setattr(settings, "join_opens_minutes_before", 10)


@pytest.fixture(autouse=True)
def no_database_for_conversations(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests run without a database, so the conversation summaries, which are
    normally written to PostgreSQL, are replaced with stand-ins."""
    monkeypatch.setattr(conversation_store, "save_summary", lambda user_id, view: None)
    monkeypatch.setattr(
        conversation_store,
        "job_code_for",
        lambda job_id: "HL-BE-01" if job_id else None,
    )
    monkeypatch.setattr(conversation_store, "job_profile_for", lambda job_id: None)
