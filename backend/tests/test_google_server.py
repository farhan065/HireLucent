"""Tests for the Google MCP server's emails and events. Nothing is sent."""

import base64
from email import message_from_bytes

import pytest

from app.mcp_clients.registry import mcp_servers
from app.mcp_servers import google_server

START = "2026-10-14T15:00:00+06:00"
END = "2026-10-14T15:45:00+06:00"


def _decode(raw: str):
    return message_from_bytes(base64.urlsafe_b64decode(raw))


def test_email_has_the_recipient_subject_and_both_bodies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(google_server.settings, "email_sender_address", "")

    message = _decode(
        google_server.build_email(
            " candidate@example.com ", "Your interview", "Plain text", "<p>HTML</p>"
        )
    )

    assert message["To"] == "candidate@example.com"
    assert message["Subject"] == "Your interview"
    assert message["From"] is None
    parts = [part.get_content_type() for part in message.walk()]
    assert "text/plain" in parts and "text/html" in parts


def test_email_is_signed_with_the_sender_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(google_server.settings, "email_sender_address", "team@example.com")
    monkeypatch.setattr(google_server.settings, "email_sender_name", "HireLucent Careers")

    message = _decode(google_server.build_email("candidate@example.com", "Hi", "Text"))

    assert message["From"] == "HireLucent Careers <team@example.com>"


@pytest.mark.parametrize(
    "address", ["not-an-address", "two@example.com, three@example.com", "a@b"]
)
def test_a_bad_address_is_refused(address: str) -> None:
    with pytest.raises(ValueError):
        google_server.build_email(address, "Hi", "Text")


def test_event_has_its_times_zone_and_one_private_guest() -> None:
    body = google_server.event_body(
        "Interview: Backend Engineer",
        "Join: http://localhost:3000/interview/abc",
        START,
        END,
        "Asia/Dhaka",
        "candidate@example.com",
    )

    assert body["start"] == {"dateTime": START, "timeZone": "Asia/Dhaka"}
    assert body["end"] == {"dateTime": END, "timeZone": "Asia/Dhaka"}
    assert body["attendees"] == [{"email": "candidate@example.com"}]
    assert body["guestsCanSeeOtherGuests"] is False
    assert "interview/abc" in body["description"]


def test_an_event_time_without_a_time_zone_is_refused() -> None:
    with pytest.raises(ValueError, match="time zone"):
        google_server.event_body(
            "Interview", "", "2026-10-14T15:00:00", END, "Asia/Dhaka", "a@example.com"
        )


class FakeEvents:
    """Records calendar calls instead of sending them."""

    def __init__(self):
        self.calls = []

    def patch(self, **kwargs):
        self.calls.append(("patch", kwargs))
        return self

    def delete(self, **kwargs):
        self.calls.append(("delete", kwargs))
        return self

    def execute(self):
        return {}


def test_cancel_saves_the_cancellation_text_quietly_then_tells_the_guest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = FakeEvents()
    monkeypatch.setattr(google_server, "_calendar", lambda: events)

    google_server.cancel_calendar_event("event-1", "Your interview has been cancelled.")

    [(first, patch), (second, delete)] = events.calls
    assert first == "patch" and patch["sendUpdates"] == "none"
    assert patch["body"] == {"description": "Your interview has been cancelled."}
    assert second == "delete" and delete["sendUpdates"] == "all"


def test_google_tools_are_backend_only() -> None:
    google = mcp_servers()["google"]

    assert google.offer_to_agent is False
    assert google.allowed_tools == {
        "send_email",
        "create_calendar_event",
        "update_calendar_event",
        "cancel_calendar_event",
    }
