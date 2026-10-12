"""The Google MCP server: interview emails and calendar invitations.

It runs in its own container and speaks MCP over HTTP, like the RAG server.
Its tools act on the outside world, so the registry never offers them to
the AI Agent: only the backend calls them, after the interviewer has
approved the interview schedule.

It uses the Google sign-in saved by scripts/google_auth.py, with two
narrow permissions: send email (it cannot read the mailbox) and manage
calendar events. Email addresses are never logged.

Run with:  python -m app.mcp_servers.google_server
"""

import base64
import re
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger, log_event
from app.services.google_client import google_service

logger = get_logger(__name__)
settings = get_settings()

# Enough to catch typing mistakes; Gmail does the real checking.
_ADDRESS = re.compile(r"^[^@\s<>,;]+@[^@\s<>,;]+\.[^@\s<>,;]+$")

server = MCPServer("HireLucent Google")


def check_address(address: str) -> str:
    """Refuse something that is clearly not one email address."""
    address = address.strip()
    if not _ADDRESS.match(address):
        raise ValueError("Not a valid email address.")
    return address


def check_time(value: str) -> str:
    """Refuse a time without its time zone, so no event lands an hour off."""
    if datetime.fromisoformat(value).tzinfo is None:
        raise ValueError("Times must include their time zone, for example +06:00.")
    return value


def build_email(to: str, subject: str, text: str, html: str | None = None) -> str:
    """The email in the encoded form the Gmail API sends."""
    message = EmailMessage()
    message["To"] = check_address(to)
    message["Subject"] = subject
    if settings.email_sender_address:
        message["From"] = formataddr(
            (settings.email_sender_name, settings.email_sender_address)
        )
    message.set_content(text)
    if html:
        message.add_alternative(html, subtype="html")
    return base64.urlsafe_b64encode(message.as_bytes()).decode()


def event_body(
    title: str,
    description: str,
    start: str,
    end: str,
    time_zone: str,
    attendee: str,
) -> dict:
    """A calendar event with the candidate as its only guest."""
    return {
        "summary": title,
        "description": description,
        "start": {"dateTime": check_time(start), "timeZone": time_zone},
        "end": {"dateTime": check_time(end), "timeZone": time_zone},
        "attendees": [{"email": check_address(attendee)}],
        # Guests cannot see or invite other guests.
        "guestsCanSeeOtherGuests": False,
        "guestsCanInviteOthers": False,
    }


def _calendar():
    return google_service("calendar", "v3").events()


def _fail(event: str, exc: Exception, message: str) -> RuntimeError:
    """Log the failure by type only and return a safe error to raise."""
    log_event(logger, event, error_type=type(exc).__name__)
    return RuntimeError(message)


@server.tool()
def send_email(to: str, subject: str, text: str, html: str | None = None) -> dict:
    """Send one email from the signed-in Gmail account. Returns its ID."""
    raw = build_email(to, subject, text, html)
    try:
        sent = (
            google_service("gmail", "v1")
            .users()
            .messages()
            .send(userId="me", body={"raw": raw})
            .execute()
        )
    except Exception as exc:
        raise _fail("email_send_failed", exc, "The email could not be sent.") from exc
    log_event(logger, "email_sent", message_id=sent["id"])
    return {"message_id": sent["id"]}


@server.tool()
def create_calendar_event(
    title: str,
    description: str,
    start: str,
    end: str,
    time_zone: str,
    attendee: str,
) -> dict:
    """Create an event in the signed-in account's calendar and send the
    guest Google's invitation. Times are ISO 8601 with a time zone offset.
    Returns the event ID."""
    body = event_body(title, description, start, end, time_zone, attendee)
    try:
        event = (
            _calendar()
            .insert(calendarId="primary", body=body, sendUpdates="all")
            .execute()
        )
    except Exception as exc:
        raise _fail(
            "event_create_failed", exc, "The calendar event could not be created."
        ) from exc
    log_event(logger, "event_created", event_id=event["id"])
    return {"event_id": event["id"]}


@server.tool()
def update_calendar_event(
    event_id: str,
    start: str,
    end: str,
    time_zone: str,
    description: str | None = None,
) -> dict:
    """Move an event to a new time, and optionally replace its description.
    The guest is told about the change."""
    body: dict = {
        "start": {"dateTime": check_time(start), "timeZone": time_zone},
        "end": {"dateTime": check_time(end), "timeZone": time_zone},
    }
    if description is not None:
        body["description"] = description
    try:
        _calendar().patch(
            calendarId="primary", eventId=event_id, body=body, sendUpdates="all"
        ).execute()
    except Exception as exc:
        raise _fail(
            "event_update_failed", exc, "The calendar event could not be moved."
        ) from exc
    log_event(logger, "event_updated", event_id=event_id)
    return {"event_id": event_id}


@server.tool()
def cancel_calendar_event(event_id: str, description: str | None = None) -> dict:
    """Delete an event. The guest receives Google's cancellation notice.

    The notice shows the event's description, so a new description can be
    given; it is saved first without telling the guest, so the guest gets
    one email."""
    try:
        if description is not None:
            _calendar().patch(
                calendarId="primary",
                eventId=event_id,
                body={"description": description},
                sendUpdates="none",
            ).execute()
        _calendar().delete(
            calendarId="primary", eventId=event_id, sendUpdates="all"
        ).execute()
    except Exception as exc:
        raise _fail(
            "event_cancel_failed", exc, "The calendar event could not be cancelled."
        ) from exc
    log_event(logger, "event_cancelled", event_id=event_id)
    return {"cancelled": True}


if __name__ == "__main__":
    configure_logging(settings)
    server.run(
        "streamable-http",
        host="0.0.0.0",
        port=settings.mcp_google_port,
        # Reachable only from other containers on the private Docker network,
        # which call it by its service name ("mcp-google").
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        ),
    )
