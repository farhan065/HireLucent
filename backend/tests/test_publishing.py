"""Tests for building the job post and publishing it. Nothing is published."""

import pytest

from app.core.errors import ServiceUnavailableError
from app.services import blogger
from app.services.job_post import post_html

DESCRIPTION = "## About the Role\nYou will build REST APIs.\n\n## Requirements\n- Python\n- SQL"
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQL/viewform"


def test_the_post_keeps_the_description_and_adds_how_to_apply() -> None:
    html = post_html(DESCRIPTION, "HL-BE-01", FORM_URL)

    assert "<h3>About the Role</h3>" in html
    assert "<li>Python</li>" in html
    assert "<h3>How to apply</h3>" in html
    assert "<strong>HL-BE-01</strong>" in html
    assert f'<a href="{FORM_URL}">Apply now</a>' in html


def test_html_in_a_description_is_shown_as_text() -> None:
    html = post_html("Hello <script>alert(1)</script>", "HL-BE-01", FORM_URL)

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def use_reply(monkeypatch: pytest.MonkeyPatch, reply: str | Exception) -> None:
    """Make the Blogger MCP server answer with the given text, or fail."""

    async def fake_create_post(title: str, html: str) -> str:
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(blogger, "_create_post", fake_create_post)


def test_the_post_address_is_read_from_the_reply(monkeypatch) -> None:
    use_reply(
        monkeypatch,
        "Successfully created post: **Backend Engineer**\n\n"
        "Post ID: 123\n"
        "URL: https://careers.example.com/2026/10/backend-engineer.html\n"
        "Published: 2026-10-07T12:00:00+06:00",
    )

    url = blogger.create_post("Backend Engineer", "<p>Body</p>")

    assert url == "https://careers.example.com/2026/10/backend-engineer.html"


def test_a_failed_publish_gives_a_clear_message(monkeypatch) -> None:
    use_reply(monkeypatch, ConnectionError("server down"))

    with pytest.raises(ServiceUnavailableError, match="could not be published"):
        blogger.create_post("Backend Engineer", "<p>Body</p>")


def test_a_reply_without_an_address_counts_as_a_failure(monkeypatch) -> None:
    use_reply(monkeypatch, "Successfully created draft: **Backend Engineer**")

    with pytest.raises(ServiceUnavailableError):
        blogger.create_post("Backend Engineer", "<p>Body</p>")
