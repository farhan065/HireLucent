"""Builds Google API clients from the sign-in saved by scripts/google_auth.py."""

from pathlib import Path
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError

NOT_CONNECTED = (
    "Google is not connected. Run the Google sign-in script, then try again."
)
SIGN_IN_EXPIRED = (
    "The Google sign-in has expired. Run the Google sign-in script again, then "
    "try again."
)


class GoogleUnavailableError(ServiceUnavailableError):
    """Google could not be used. The message is safe to show."""

    code = "google_unavailable"


def google_service(name: str, version: str) -> Any:
    """A client for one Google API, for example ("forms", "v1")."""
    token_file = Path(get_settings().google_token_file)
    if not token_file.exists():
        raise GoogleUnavailableError(NOT_CONNECTED)
    credentials = Credentials.from_authorized_user_file(str(token_file))
    return build(name, version, credentials=credentials, cache_discovery=False)
