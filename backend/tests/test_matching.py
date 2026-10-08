"""Tests for semantic matching. The vector store and the AI are replaced
with stand-ins, so only our own logic is tested here."""

import pytest

from app.graphs.screening import matching
from app.graphs.screening.matching import MatchAnswer

PARSED = {
    "summary": "Backend engineer.",
    "skills": ["Python", "Django"],
    "experience": [
        {
            "title": "Engineer",
            "company": "Example Soft",
            "start": "2020",
            "end": "Present",
            "description": "Built REST services in Django.",
        }
    ],
    "projects": [{"name": "Billing", "description": "Invoices.", "technologies": ["Celery"]}],
    "education": [{"degree": "BSc", "field": "Computer Science", "year": "2019"}],
    "certifications": [],
    "contact": {"emails": ["sample@example.com"], "phones": [], "links": []},
}
CV_TEXT = "Sample Person sample@example.com\nBuilt REST services in Django.\nBSc 2019"
REQUIREMENTS = {
    "items": [
        {
            "id": "R1",
            "text": "Python web development",
            "category": "technical_skills",
            "priority": "must_have",
            "keywords": ["django"],
        },
        {
            "id": "R2",
            "text": "Cloud experience",
            "category": "technical_skills",
            "priority": "preferred",
            "keywords": ["aws"],
        },
    ]
}


class FakeCollection:
    """Records what is stored, and returns every section for each query."""

    def __init__(self) -> None:
        self.documents: list[str] = []
        self.metadatas: list[dict] = []
        self.deleted: list[dict] = []

    def delete(self, where: dict) -> None:
        self.deleted.append(where)

    def add(self, ids, documents, embeddings, metadatas) -> None:
        self.documents, self.metadatas = documents, metadatas

    def query(self, query_embeddings, n_results, where) -> dict:
        return {"documents": [self.documents[:n_results] for _ in query_embeddings]}


@pytest.fixture
def collection(monkeypatch: pytest.MonkeyPatch) -> FakeCollection:
    fake = FakeCollection()
    monkeypatch.setattr(matching.rag_store, "get_collection", lambda name: fake)
    monkeypatch.setattr(matching.ai_client, "embed_texts", lambda texts: [[0.1]] * len(texts))
    return fake


def use_ai(monkeypatch: pytest.MonkeyPatch, answer: MatchAnswer) -> list[str]:
    prompts: list[str] = []

    def fake(prompt: str, schema: type) -> MatchAnswer:
        prompts.append(prompt)
        return answer

    monkeypatch.setattr(matching.ai_client, "generate_structured", fake)
    return prompts


def test_the_cv_is_split_into_sections() -> None:
    sections = dict(matching.cv_sections(PARSED))

    assert sections["experience"] == (
        "Engineer at Example Soft (2020 to Present): Built REST services in Django."
    )
    assert "Celery" in sections["project"]
    assert sections["education"] == "Education: BSc, Computer Science, 2019"
    assert "certifications" not in sections


def test_sections_are_stored_with_the_candidate_and_job(collection) -> None:
    matching.index_cv(7, 3, PARSED)

    assert collection.deleted == [{"candidate_id": 7}]
    assert collection.metadatas[0] == {"candidate_id": 7, "job_id": 3, "section": "summary"}


def test_every_requirement_gets_a_result(monkeypatch, collection) -> None:
    answer = MatchAnswer(
        matches=[
            {
                "id": "R1",
                "status": "met",
                "evidence": "built REST services in Django",
                "reason": "Django web services.",
            }
        ]
    )
    prompts = use_ai(monkeypatch, answer)

    matches = matching.match(7, 3, REQUIREMENTS, {"parsed": PARSED, "text": CV_TEXT})

    assert [item["id"] for item in matches] == ["R1", "R2"]
    assert matches[0]["status"] == "met"
    assert matches[0]["evidence_in_cv"] is True
    assert matches[0]["priority"] == "must_have"
    # A requirement the AI skipped is recorded as unmet with the reason.
    assert matches[1]["status"] == "unmet"
    assert "no answer" in matches[1]["reason"]
    assert "R1 (must-have): Python web development" in prompts[0]
    assert "sample@example.com" not in prompts[0]


def test_evidence_not_found_in_the_cv_is_flagged(monkeypatch, collection) -> None:
    answer = MatchAnswer(
        matches=[{"id": "R1", "status": "met", "evidence": "led a team of 40 engineers"}]
    )
    use_ai(monkeypatch, answer)

    matches = matching.match(7, 3, REQUIREMENTS, {"parsed": PARSED, "text": CV_TEXT})

    assert matches[0]["evidence_in_cv"] is False

