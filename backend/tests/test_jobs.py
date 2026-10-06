"""Tests for job requirement rules and job code generation."""

import pytest
from pydantic import ValidationError

from app.schemas.job import JobRequirements, RequirementItem, ScoringWeights
from app.services.job_service import build_job_code


def _item(**changes) -> dict:
    item = {
        "id": "R1",
        "text": "Python web development",
        "category": "technical_skills",
        "priority": "must_have",
        "keywords": ["Python", " django ", "python", ""],
    }
    return item | changes


def test_keywords_are_cleaned() -> None:
    item = RequirementItem(**_item())

    assert item.keywords == ["python", "django"]


def test_requirement_about_a_protected_characteristic_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RequirementItem(**_item(text="Male candidates under age 30"))


def test_job_related_words_are_not_mistaken_for_protected_terms() -> None:
    item = RequirementItem(**_item(text="Team management and storage design"))

    assert item.text == "Team management and storage design"


def test_unknown_category_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RequirementItem(**_item(category="personality"))


def test_requirement_ids_must_be_unique() -> None:
    with pytest.raises(ValidationError):
        JobRequirements(items=[_item(), _item()])


def test_a_job_needs_at_least_one_requirement() -> None:
    with pytest.raises(ValidationError):
        JobRequirements(items=[])


def test_weights_must_add_up_to_one() -> None:
    ScoringWeights(technical_skills=0.5, experience=0.3, qualifications=0.2)

    with pytest.raises(ValidationError):
        ScoringWeights(technical_skills=0.5, experience=0.5, qualifications=0.5)


def test_first_job_code_uses_title_initials() -> None:
    assert build_job_code("Backend Engineer (Python)", []) == "HL-BE-01"


def test_job_code_number_continues_after_the_highest_in_use() -> None:
    existing = ["HL-BE-01", "HL-BE-03", "HL-FE-01"]

    assert build_job_code("Business Executive", existing) == "HL-BE-04"
    assert build_job_code("Frontend Engineer", existing) == "HL-FE-02"


def test_one_word_title_uses_its_first_two_letters() -> None:
    assert build_job_code("Designer", []) == "HL-DE-01"