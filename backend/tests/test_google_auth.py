"""Tests for the Google sign-in script's helpers. No sign-in happens here."""

from datetime import datetime

from google.oauth2.credentials import Credentials

from scripts.google_auth import SCOPES, blogger_tokens, missing_scopes


def make_credentials(scopes: list[str]) -> Credentials:
    return Credentials(
        token="access",
        refresh_token="refresh",
        scopes=scopes,
        expiry=datetime(2026, 10, 7, 12, 0, 0),
    )


def test_blogger_tokens_use_the_format_the_mcp_server_reads() -> None:
    tokens = blogger_tokens(make_credentials(SCOPES))

    assert tokens["access_token"] == "access"
    assert tokens["refresh_token"] == "refresh"
    assert tokens["token_type"] == "Bearer"
    assert tokens["scope"].split() == SCOPES
    # Milliseconds since 1970 for 07 Oct 2026 12:00 UTC.
    assert tokens["expiry_date"] == 1791374400000


def test_all_permissions_granted_means_nothing_is_missing() -> None:
    assert missing_scopes(make_credentials(SCOPES)) == []


def test_an_unticked_permission_is_reported() -> None:
    credentials = make_credentials(SCOPES[:-1])

    assert missing_scopes(credentials) == [SCOPES[-1]]
