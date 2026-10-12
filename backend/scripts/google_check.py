"""Check the Google MCP server and the Google sign-in it uses.

By default nothing is sent: it checks that the server answers with its
tools, that the sign-in has the email and calendar permissions, and that
the calendar can be read. With --send-test-to it also sends one test email
through the server, so you can see it arrive.

Usage (inside the backend container):
    python -m scripts.google_check
    python -m scripts.google_check --send-test-to you@example.com
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from mcp import Client

from app.core.config import get_settings
from app.mcp_clients import client
from app.mcp_clients.registry import mcp_servers
from app.services.google_client import google_service

NEEDED_SCOPES = {
    "https://www.googleapis.com/auth/gmail.send": "send email",
    "https://www.googleapis.com/auth/calendar.events": "calendar events",
}


async def list_tools() -> None:
    server = mcp_servers()["google"]
    async with Client(server.url) as connection:
        listed = [tool.name for tool in (await connection.list_tools()).tools]
    print("Server tools:", listed)
    missing = sorted(server.allowed_tools - set(listed))
    if missing:
        sys.exit(f"The server does not list these allowed tools: {missing}")


def check_scopes() -> None:
    token_file = Path(get_settings().google_token_file)
    if not token_file.exists():
        sys.exit("No Google sign-in found. Run python -m scripts.google_auth first.")
    granted = set(json.loads(token_file.read_text(encoding="utf-8")).get("scopes", []))
    missing = [label for scope, label in NEEDED_SCOPES.items() if scope not in granted]
    if missing:
        sys.exit(
            "The Google sign-in is missing: " + ", ".join(missing)
            + ". Run python -m scripts.google_auth again on your computer."
        )
    print("Sign-in permissions: send email and calendar events are granted.")


def check_calendar() -> None:
    events = google_service("calendar", "v3").events()
    events.list(calendarId="primary", maxResults=1).execute()
    print("Calendar: reachable.")


def send_test(address: str) -> None:
    result = client.call_tool(
        "google",
        "send_email",
        {
            "to": address,
            "subject": "HireLucent test email",
            "text": "This is a test email from HireLucent. No action is needed.",
        },
    )
    if result.is_error:
        sys.exit("The test email could not be sent. See the mcp-google logs.")
    print("Test email sent. Check the inbox.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--send-test-to", metavar="ADDRESS")
    args = parser.parse_args()

    asyncio.run(list_tools())
    check_scopes()
    check_calendar()
    if args.send_test_to:
        send_test(args.send_test_to)


if __name__ == "__main__":
    main()
