"""Job-relevant-only scoring checks (BID N16 data minimisation, N20
fairness): every AI step that judges a candidate is told to ignore personal
traits, and the inputs built for it carry job-related facts only, with
contact details masked. Personal fields stored with the candidate (name,
photo, face code, identity check) never reach a scoring prompt."""

import pytest

from app.graphs.feedback import writing
from app.graphs.final_assessment import claims, report
from app.graphs.interview_quality import recommendations
from app.graphs.qa_analysis import evaluation, segmentation
from app.graphs.screening import matching, parsing, scoring
from app.models.enums import Speaker

EMAIL = "rahim.uddin@example.com"
PHONE = "+880 1711 223344"
LINK = "linkedin.com/in/rahim-uddin"
CONTACTS = (EMAIL, PHONE, LINK)
# Fields that are stored with a candidate but must never be scored.
PERSONAL = ("Rahim Uddin", "photos/4f1c.jpg", "0.61", "verified", "34 years old", "male")


class Captured(Exception):
    """Stops the AI call once the prompt is seen."""


@pytest.fixture()
def prompts(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every prompt sent to the AI, instead of calling it."""
    sent: list[str] = []

    def capture(prompt: str, schema):
        sent.append(prompt)
        raise Captured

    for module in (scoring, matching):
        monkeypatch.setattr(module.ai_client, "generate_structured", capture)
    return sent


def assert_job_facts_only(text: str) -> None:
    for value in CONTACTS + PERSONAL:
        assert value not in text


# --- The instructions ----------------------------------------------------------

JUDGING_PROMPTS = {
    "CV matching": matching.PROMPT,
    "CV scoring": scoring.PROMPT,
    "answer evaluation": evaluation.PROMPT,
    "interview report": report.PROMPT,
    "CV claim check": claims.PROMPT,
    "interview quality recommendations": recommendations.PROMPT,
    "feedback email": writing.PROMPT,
    "feedback email review": writing.REVIEW_PROMPT,
}


@pytest.mark.parametrize("name", JUDGING_PROMPTS)
def test_every_ai_step_that_judges_is_told_to_ignore_personal_traits(name: str) -> None:
    prompt = JUDGING_PROMPTS[name].lower()

    assert "personal trait" in prompt or "gender" in prompt, name


def test_cv_reading_extracts_no_personal_characteristics() -> None:
    prompt = parsing.PROMPT.lower()

    for word in ("age", "gender", "nationality", "religion", "marital status", "photo"):
        assert word in prompt  # listed under "Do not extract or mention"
    assert "do not extract" in prompt


# --- What the AI is given --------------------------------------------------------


def test_cv_text_is_read_with_contact_details_masked(monkeypatch) -> None:
    sent: list[str] = []

    def capture(prompt: str, schema):
        sent.append(prompt)
        raise Captured

    monkeypatch.setattr(parsing, "generate_structured", capture)
    cv = f"Rahim Uddin\n{EMAIL} | {PHONE} | {LINK}\nBackend developer, 4 years of Python."

    with pytest.raises(Captured):
        parsing.parse_cv(cv)

    for value in CONTACTS:
        assert value not in sent[0]
    assert "[email]" in sent[0] and "[phone]" in sent[0] and "[link]" in sent[0]


def test_screening_scores_use_requirement_results_and_cv_facts_only(prompts) -> None:
    parsed = {
        "summary": "Rahim Uddin is a backend developer.",
        "total_experience_years": 4,
        "education": [{"degree": "BSc", "field": "CSE", "institution": "BUET"}],
        "certifications": ["AWS Certified Developer"],
        "contact": {"emails": [EMAIL], "phones": [PHONE], "links": [LINK]},
        # Stored with the candidate or the application, never for scoring.
        "full_name": "Rahim Uddin",
        "photo_path": "photos/4f1c.jpg",
        "identity": {"result": "verified", "score": 0.61},
        "age": "34 years old",
        "gender": "male",
    }
    matches = [
        {
            "id": "R1",
            "category": "technical_skills",
            "priority": "must_have",
            "text": "Python",
            "status": "met",
            "evidence": "4 years of Python",
            "reason": "Stated in the work experience.",
        }
    ]

    with pytest.raises(Captured):
        scoring.dimension_scores("Backend Engineer", {"min_experience_years": 2}, matches, parsed)

    assert_job_facts_only(prompts[0])
    assert "R1" in prompts[0] and "BSc" in prompts[0] and "AWS" in prompts[0]


def test_cv_parts_reach_the_matcher_with_contact_details_masked(prompts, monkeypatch) -> None:
    part = f"Backend developer. Reach me at {EMAIL}, {PHONE} or {LINK}."
    monkeypatch.setattr(matching, "index_cv", lambda candidate_id, job_id, parsed: [part])
    monkeypatch.setattr(
        matching, "closest_sections", lambda candidate_id, items, count: [[part]]
    )
    cv = {"parsed": {"contact": {"emails": [EMAIL], "phones": [PHONE], "links": [LINK]}}}
    requirements = {"items": [{"id": "R1", "priority": "must_have", "text": "Python"}]}

    with pytest.raises(Captured):
        matching.match(3, 2, requirements, cv)

    for value in CONTACTS:
        assert value not in prompts[0]
    assert "[email]" in prompts[0]


TURNS = {
    1: {
        "id": 1,
        "speaker": Speaker.INTERVIEWER,
        "start_ms": 0,
        "text": "How did you scale the API?",
    },
    2: {
        "id": 2,
        "speaker": Speaker.CANDIDATE,
        "start_ms": 4000,
        "text": f"With a queue and caching. You can mail me at {EMAIL} or call {PHONE}.",
    },
}
PAIR = {
    "id": "Q1",
    "kind": "technical",
    "question": "How did you scale the API?",
    "question_turn_ids": [1],
    "answer_turn_ids": [2],
    "requirement_ids": ["R1"],
    "evaluation": {"score": 80, "answered": "answered", "justification": "Clear approach."},
}


def test_the_transcript_reaches_every_interview_ai_step_with_contacts_masked() -> None:
    inputs = {
        "segmentation": segmentation.transcript_lines(list(TURNS.values())),
        "answer evaluation": evaluation.batch_lines([PAIR], TURNS, {}),
        "report": report.answer_lines([PAIR], TURNS),
        "CV claim check": claims.answer_lines([PAIR], TURNS),
    }

    for name, text in inputs.items():
        for value in CONTACTS:
            assert value not in text, name
        assert "queue and caching" in text, name


def test_cv_claims_are_compared_with_job_facts_and_contacts_masked() -> None:
    cv = {
        "total_experience_years": 4,
        "experience": [
            {
                "title": "Backend Developer",
                "company": "Acme",
                "start": "2021",
                "end": "Present",
                "description": f"Built APIs. Portfolio: {LINK}",
            }
        ],
        "skills": ["Python"],
        "contact": {"emails": [EMAIL], "phones": [PHONE], "links": [LINK]},
        "photo_path": "photos/4f1c.jpg",
        "gender": "male",
    }

    text = claims.claim_lines(claims.extract_claims(cv))

    assert_job_facts_only(text)
    assert "Backend Developer" in text and "Python" in text
