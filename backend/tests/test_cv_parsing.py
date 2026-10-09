"""Tests for reading a CV into structured facts. The AI is replaced with a
stand-in that records the prompt it was given."""

import pytest

from app.graphs.screening import parsing
from app.schemas.cv import CVContent

CV_TEXT = """Sample Person
sample.person@example.com | +880 1712-345678 | linkedin.com/in/sample-person
https://github.com/sample-person

Backend Engineer, Example Soft (Jan 2019 - Dec 2023)
Built REST APIs with Python and FastAPI for 2000 daily users.

BSc in Computer Science, Example University, 2014 - 2018
"""

CONTENT = CVContent(
    summary="Backend engineer.",
    skills=["Python", "FastAPI"],
    education=[{"degree": "BSc", "field": "Computer Science", "year": "2018"}],
    experience=[{"title": "Backend Engineer", "company": "Example Soft"}],
    total_experience_years=5,
    certifications=[],
    projects=[],
)


@pytest.fixture
def prompts(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    seen: list[str] = []

    def fake_generate(prompt: str, schema: type) -> CVContent:
        seen.append(prompt)
        return CONTENT

    monkeypatch.setattr(parsing, "generate_structured", fake_generate)
    return seen


def test_contact_details_are_found() -> None:
    contact = parsing.find_contact(CV_TEXT)

    assert contact.emails == ["sample.person@example.com"]
    assert contact.phones == ["+880 1712-345678"]
    assert contact.links == [
        "linkedin.com/in/sample-person",
        "https://github.com/sample-person",
    ]


@pytest.mark.parametrize(
    "text",
    ["Jan 2019 - Dec 2023", "2014 - 2018", "2019-01 - 2023-12", "2000 daily users"],
)
def test_dates_and_numbers_are_not_taken_for_phone_numbers(text: str) -> None:
    assert parsing.find_contact(text).phones == []


@pytest.mark.parametrize("phone", ["01712345678", "(555) 123-4567", "+44 20 7946 0958"])
def test_common_phone_formats_are_found(phone: str) -> None:
    assert parsing.find_contact(f"Phone: {phone}").phones == [phone]


def test_the_ai_never_receives_contact_details(prompts: list[str]) -> None:
    parsing.parse_cv(CV_TEXT)

    prompt = prompts[0]
    assert "sample.person@example.com" not in prompt
    assert "1712" not in prompt
    assert "linkedin.com" not in prompt
    assert "github.com" not in prompt
    assert "[email]" in prompt and "[phone]" in prompt and "[link]" in prompt
    # The job-related content is still there.
    assert "Jan 2019 - Dec 2023" in prompt
    assert "FastAPI" in prompt


def test_parsed_cv_holds_the_ai_facts_and_the_contact_details(prompts: list[str]) -> None:
    parsed = parsing.parse_cv(CV_TEXT)

    assert parsed["skills"] == ["Python", "FastAPI"]
    assert parsed["education"][0]["field"] == "Computer Science"
    assert parsed["total_experience_years"] == 5
    assert parsed["contact"]["emails"] == ["sample.person@example.com"]


def test_a_very_long_cv_is_cut_before_it_is_sent(prompts: list[str]) -> None:
    parsing.parse_cv("Python developer. " * 5000)

    assert len(prompts[0]) < parsing.MAX_CV_CHARS + len(parsing.PROMPT)


def test_cv_facts_shown_to_the_interviewer_leave_out_emails_and_phones() -> None:
    from app.models import Candidate

    parsed = CONTENT.model_dump() | {
        "contact": {
            "emails": ["sample.person@example.com"],
            "phones": ["+880 1712-345678"],
            "links": ["https://github.com/sample-person"],
        }
    }

    facts = Candidate(cv_parsed=parsed).cv_facts

    assert facts["skills"] == ["Python", "FastAPI"]
    assert facts["links"] == ["https://github.com/sample-person"]
    assert "contact" not in facts
    assert "sample.person@example.com" not in str(facts)
    assert "1712" not in str(facts)


def test_a_cv_not_read_yet_has_no_facts() -> None:
    from app.models import Candidate

    assert Candidate(cv_parsed=None).cv_facts is None
