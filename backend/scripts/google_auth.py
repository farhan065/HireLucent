"""Sign in to Google once and save the tokens the app uses.

Run this on your own computer, not in Docker, because it opens a browser:

    cd backend
    python -m scripts.google_auth

It reads secrets/google_client.json and writes two files beside it:
google_token.json for the backend, and blogger_tokens.json for the Blogger
MCP server. Both hold the same sign-in. While the Google Cloud app is in
Testing mode the sign-in lasts about 7 days, then this must be run again.
"""

import json
import os
import sys
from datetime import UTC
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SECRETS_DIR = Path(__file__).resolve().parents[2] / "secrets"
CLIENT_FILE = SECRETS_DIR / "google_client.json"
TOKEN_FILE = SECRETS_DIR / "google_token.json"
BLOGGER_TOKEN_FILE = SECRETS_DIR / "blogger_tokens.json"

# Only what the app does: publish posts, read the application form and its
# responses, and download the CVs uploaded through the form.
SCOPES = [
    "https://www.googleapis.com/auth/blogger",
    "https://www.googleapis.com/auth/forms.body.readonly",
    "https://www.googleapis.com/auth/forms.responses.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def blogger_tokens(credentials: Credentials) -> dict:
    """The sign-in in the format the Blogger MCP server reads."""
    expiry = credentials.expiry.replace(tzinfo=UTC)
    return {
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "scope": " ".join(credentials.scopes or []),
        "token_type": "Bearer",
        "expiry_date": int(expiry.timestamp() * 1000),
    }


def missing_scopes(credentials: Credentials) -> list[str]:
    """Permissions that were asked for but not ticked on the consent screen."""
    granted = set(credentials.granted_scopes or credentials.scopes or [])
    return [scope for scope in SCOPES if scope not in granted]


def main() -> None:
    if not CLIENT_FILE.exists():
        sys.exit(f"Missing {CLIENT_FILE}. Download the OAuth client JSON first.")

    # Let a partly ticked consent screen reach the clear message below.
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_FILE), SCOPES)
    credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    missing = missing_scopes(credentials)
    if missing:
        sys.exit(
            "Not saved: tick every permission on the consent screen and run "
            "this again. Missing: " + ", ".join(missing)
        )
    if not credentials.refresh_token:
        sys.exit("Not saved: Google did not return a refresh token. Run this again.")

    TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")
    BLOGGER_TOKEN_FILE.write_text(
        json.dumps(blogger_tokens(credentials), indent=2), encoding="utf-8"
    )
    print("Signed in. Saved google_token.json and blogger_tokens.json in secrets/.")


if __name__ == "__main__":
    main()
