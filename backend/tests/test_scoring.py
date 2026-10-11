"""Tests for scoring. The embedding model and the AI are replaced."""

import pytest
from pydantic import ValidationError

from app.graphs.screening import scoring
from app.graphs.screening.scoring import DimensionScores

REQUIREMENTS = {
    "min_experience_years": 3,
    "items": [
        {"id": "R1", "keywords": ["django", "fastapi"]},
        {"id": "R2", "keywords": ["postgresql", "kubernetes"]},
    ],
}
CV = "Sample Person sample@example.com. Built REST services in Django on PostgreSQL."
MATCHES = [
    {
        "id": "R1",
        "text": "Python web development",
        "priority": "must_have",
        "category": "technical_skills",
        "status": "met",
        "evidence": "Built REST services in Django",
        "reason": "Django web services.",
    },
    {
        "id": "R3",
        "text": "Degree in computer science",
        "priority": "preferred",
        "category": "qualifications",
        "status": "unmet",
        "evidence": "",
        "reason": "No degree stated.",
    },
]
GOOD = {
    "technical_skills": {"score": 88, "justification": "Django and PostgreSQL cover the stack."},
    "experience": {"score": 80, "justification": "Four years in backend roles."},
    "qualifications": {"score": 40, "justification": "No degree is stated in the CV."},
}
SUMMARY = "Strong Django and PostgreSQL work. No degree is stated, which lowers the score."


def test_ats_score_averages_keyword_coverage_and_similarity(monkeypatch) -> None:
    texts: list[list[str]] = []

    def fake_embed(batch: list[str]) -> list[list[float]]:
        texts.append(batch)
        return [[1.0, 0.0], [0.6, 0.8]]  # cosine 0.6

    monkeypatch.setattr(scoring.ai_client, "embed_texts", fake_embed)

    ats = scoring.ats_score(REQUIREMENTS, "Backend job", CV)

    assert ats["keywords_found"] == ["django", "postgresql"]
    assert ats["keywords_missing"] == ["fastapi", "kubernetes"]
    assert ats["keyword_coverage"] == 50.0
    assert ats["similarity"] == 60.0
    assert ats["score"] == 55.0
    # Contact details are masked before the CV is embedded.
    assert "sample@example.com" not in texts[0][0]


def test_the_ai_gets_the_evidence_grouped_by_dimension(monkeypatch) -> None:
    prompts: list[str] = []

    def fake_ai(prompt: str, schema: type) -> DimensionScores:
        prompts.append(prompt)
        return DimensionScores(**GOOD, summary=SUMMARY)

    monkeypatch.setattr(scoring.ai_client, "generate_structured", fake_ai)
    parsed = {"total_experience_years": 4, "education": [], "certifications": []}

    answer = scoring.dimension_scores("Backend Engineer", REQUIREMENTS, MATCHES, parsed)

    assert answer["dimensions"]["technical_skills"] == GOOD["technical_skills"]
    assert answer["summary"] == SUMMARY
    prompt = prompts[0]
    assert 'R1 (must-have) Python web development: met. Evidence: "Built REST' in prompt
    assert "Relevant experience:\n- No requirements." in prompt
    assert "Minimum years of experience: 3" in prompt


@pytest.mark.parametrize(
    "bad",
    [
        {"score": 120, "justification": "Far too high a score here."},
        {"score": 80, "justification": ""},
    ],
)
def test_an_invalid_answer_is_rejected(bad: dict) -> None:
    with pytest.raises(ValidationError):
        DimensionScores(**(GOOD | {"experience": bad}), summary=SUMMARY)


def test_a_missing_summary_is_rejected() -> None:
    with pytest.raises(ValidationError):
        DimensionScores(**GOOD, summary="Good.")


def test_final_score_is_weighted_and_combined_with_ats() -> None:
    weights = {"technical_skills": 0.5, "experience": 0.3, "qualifications": 0.2}

    totals = scoring.combine(GOOD, weights, ats=73)

    # 88 x 0.5 + 80 x 0.3 + 40 x 0.2 = 76; 0.8 x 76 + 0.2 x 73 = 75.4
    assert totals == {"criteria_score": 76.0, "final_score": 75.4}


def test_final_order_breaks_ties_by_criteria_score_then_name() -> None:
    candidates = [
        {"candidate_id": 1, "full_name": "Zara", "final_score": 70.0, "criteria_score": 72.0},
        {"candidate_id": 2, "full_name": "Adam", "final_score": 70.0, "criteria_score": 72.0},
        {"candidate_id": 3, "full_name": "Mina", "final_score": 70.0, "criteria_score": 80.0},
        {"candidate_id": 4, "full_name": "Omar", "final_score": 85.0, "criteria_score": 60.0},
    ]

    assert scoring.final_order(candidates) == [4, 3, 2, 1]
