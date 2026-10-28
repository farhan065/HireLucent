"""Tests for the must-have rules. The AI is replaced with a stand-in."""

import pytest

from app.graphs.screening import must_haves
from app.graphs.screening.must_haves import MustHaveAnswers

CV = (
    "Sample Person, sample@example.com\n"
    "Built REST services in Django on AWS EKS. Knows C++ and Node.js."
)


def item(item_id: str, text: str, keywords: list[str], priority: str = "must_have") -> dict:
    return {"id": item_id, "text": text, "priority": priority, "keywords": keywords}


@pytest.mark.parametrize(
    ("keyword", "found"),
    [
        ("django", True),
        ("rest services", True),
        ("c++", True),
        ("node.js", True),
        ("eks", True),
        ("java", False),
        ("rest", True),
        ("services in", True),
        ("aw", False),
    ],
)
def test_keywords_are_matched_as_whole_words(keyword: str, found: bool) -> None:
    assert must_haves.keyword_found(keyword, CV) is found


def test_javascript_does_not_count_as_java() -> None:
    assert not must_haves.keyword_found("java", "Five years of JavaScript.")


@pytest.mark.parametrize(
    ("minimum", "years", "excluded"),
    [(5, 2, True), (5, 5, False), (5, 7.5, False), (5, 0, False), (0, 1, False)],
)
def test_experience_rule(minimum: int, years: float, excluded: bool) -> None:
    assert (must_haves.experience_shortfall(minimum, years) is not None) is excluded


def test_preferred_requirements_are_never_checked(monkeypatch) -> None:
    monkeypatch.setattr(must_haves, "generate_structured", lambda p, s: pytest.fail("no AI"))
    requirements = {"items": [item("R1", "Go programming", ["golang"], "preferred")]}

    assert must_haves.check(requirements, CV, {"total_experience_years": 3}) == []


def test_the_ai_is_asked_only_about_must_haves_without_a_keyword(monkeypatch) -> None:
    prompts: list[str] = []

    def fake_ai(prompt: str, schema: type) -> MustHaveAnswers:
        prompts.append(prompt)
        return MustHaveAnswers(answers=[{"id": "R2", "shown": True}])

    monkeypatch.setattr(must_haves, "generate_structured", fake_ai)
    requirements = {
        "min_experience_years": 0,
        "items": [
            item("R1", "Python web development", ["django", "flask"]),
            item("R2", "Container orchestration", ["kubernetes"]),
        ],
    }

    assert must_haves.check(requirements, CV, {"total_experience_years": 4}) == []
    assert "R2: Container orchestration" in prompts[0]
    assert "R1" not in prompts[0]
    # Contact details are masked before the CV reaches the AI.
    assert "sample@example.com" not in prompts[0]


def test_a_requirement_the_ai_does_not_answer_is_not_held_against_anyone(monkeypatch) -> None:
    empty = MustHaveAnswers(answers=[])
    monkeypatch.setattr(must_haves, "generate_structured", lambda p, s: empty)
    requirements = {"items": [item("R1", "Container orchestration", ["kubernetes"])]}

    assert must_haves.check(requirements, "Python developer", {}) == []
