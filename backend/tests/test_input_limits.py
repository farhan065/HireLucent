"""Input limits added in Core Hardening (BID N8): oversized input is refused
with a validation error instead of being stored or sent to the AI."""

import pytest
from pydantic import ValidationError

from app.schemas.assessment import AddQuestionsRequest, ReviewRequest
from app.schemas.chat import ChatMessageRequest
from app.schemas.job import MAX_KEYWORDS, MAX_REQUIREMENTS, JobRequirements


def _item(number: int, keywords: list[str] | None = None) -> dict:
    return {
        "id": f"R{number}",
        "text": f"Requirement number {number}",
        "category": "technical_skills",
        "priority": "must_have",
        "keywords": keywords or ["python"],
    }


def test_a_job_can_have_up_to_the_limit_of_requirements() -> None:
    items = [_item(n) for n in range(1, MAX_REQUIREMENTS + 1)]

    assert len(JobRequirements(min_experience_years=2, items=items).items) == MAX_REQUIREMENTS
    with pytest.raises(ValidationError):
        JobRequirements(min_experience_years=2, items=items + [_item(MAX_REQUIREMENTS + 1)])


def test_keywords_are_limited_in_number_and_length() -> None:
    too_many = [f"skill{n}" for n in range(MAX_KEYWORDS + 1)]

    with pytest.raises(ValidationError):
        JobRequirements(min_experience_years=0, items=[_item(1, too_many)])
    with pytest.raises(ValidationError):
        JobRequirements(min_experience_years=0, items=[_item(1, ["x" * 81])])


def test_ids_sent_back_by_the_screens_are_short() -> None:
    with pytest.raises(ValidationError):
        AddQuestionsRequest(pair_ids=["Q" * 21])
    with pytest.raises(ValidationError):
        ReviewRequest(action="edit", remove=["S" * 21])


def test_a_chat_thread_id_is_short() -> None:
    with pytest.raises(ValidationError):
        ChatMessageRequest(thread_id="t" * 101, message="Hello")
