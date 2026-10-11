"""Shared test setup."""

import pytest

from app.services import conversation_store


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
