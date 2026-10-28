"""Changing a saved job before it is published, and showing the
interviewer's change requests in the conversation."""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.core.errors import ConflictError
from app.graphs.recruiter import tools
from app.graphs.recruiter.prompts import SYSTEM_PROMPT
from app.models.enums import JobStatus
from app.schemas.job import JobRequirements, ScoringWeights
from app.services import chat_service, job_service
from tests.helpers import DRAFT_ONE, DRAFT_TWO, VALID_ARGS, graph_with_replies, save_call


@contextmanager
def _no_database():
    yield None


def _saved_state(*drafts: str) -> dict:
    return {
        "saved_job_id": 7,
        "user_id": 1,
        "messages": [AIMessage(draft) for draft in drafts],
    }


def _job(status: JobStatus) -> SimpleNamespace:
    return SimpleNamespace(id=7, job_code="HL-BE-01", status=status)


@pytest.fixture
def updates(monkeypatch) -> list[dict]:
    """Record what the job is updated with, without a database."""
    recorded: list[dict] = []
    monkeypatch.setattr(tools, "SessionLocal", _no_database)
    monkeypatch.setattr(
        tools.job_service, "get_job", lambda db, job_id: _job(JobStatus.APPROVED)
    )

    def fake_update(db, job_id, **changes):
        recorded.append({"job_id": job_id, **changes})
        return _job(JobStatus.APPROVED)

    monkeypatch.setattr(tools.job_service, "update_unpublished_job", fake_update)
    return recorded


def test_saving_again_before_publishing_updates_the_job(updates) -> None:
    message, changes = tools.save_job(VALID_ARGS, _saved_state(DRAFT_ONE, DRAFT_TWO))

    assert changes == {}
    assert message.startswith("Job saved again with job code HL-BE-01")
    [update] = updates
    assert update["job_id"] == 7
    # The newest description is the one saved.
    assert update["title"] == "Senior Backend Engineer"
    assert "lead the design" in update["jd_text"]
    assert update["requirements"].min_experience_years == 2


def test_a_published_job_cannot_be_saved_again(monkeypatch, updates) -> None:
    monkeypatch.setattr(
        tools.job_service, "get_job", lambda db, job_id: _job(JobStatus.PUBLISHED)
    )

    with pytest.raises(ConflictError, match="already published"):
        tools.save_job(VALID_ARGS, _saved_state(DRAFT_ONE))
    assert updates == []


def test_saving_again_still_needs_a_description(updates) -> None:
    state = {"saved_job_id": 7, "user_id": 1, "messages": [HumanMessage("Change it")]}

    with pytest.raises(ConflictError):
        tools.save_job(VALID_ARGS, state)
    assert updates == []


def test_the_service_refuses_a_published_job(monkeypatch) -> None:
    monkeypatch.setattr(job_service, "get_job", lambda db, job_id: _job(JobStatus.PUBLISHED))

    with pytest.raises(ConflictError):
        job_service.update_unpublished_job(
            None,
            7,
            title="Backend Engineer",
            jd_text="Text",
            requirements=JobRequirements.model_validate(VALID_ARGS["requirements"]),
            scoring_weights=ScoringWeights.model_validate(VALID_ARGS["scoring_weights"]),
        )


def test_the_prompt_keeps_description_and_requirements_in_step() -> None:
    assert "The description and the requirements must always match" in SYSTEM_PROMPT
    assert "first reply with the" in SYSTEM_PROMPT
    assert "full revised description" in SYSTEM_PROMPT


def test_a_change_request_is_shown_under_the_changed_card(monkeypatch) -> None:
    graph = graph_with_replies(
        monkeypatch,
        [AIMessage(DRAFT_ONE), save_call(VALID_ARGS), AIMessage(DRAFT_TWO)],
    )
    first = chat_service.send_message(graph, 1, None, "I need a backend engineer")
    chat_service.send_message(graph, 1, first.thread_id, "I approve this.")

    view = chat_service.send_message(
        graph, 1, first.thread_id, "Change the experience from 3 years to 2 years"
    )

    kinds = [item.kind for item in view.items]
    card = kinds.index("requirements")
    assert view.items[card].status == "changed"
    feedback = view.items[card + 1]
    assert (feedback.kind, feedback.text) == (
        "user",
        "Change the experience from 3 years to 2 years",
    )
    # The revised description follows the interviewer's message.
    assert view.items[card + 2].kind == "description"


def test_a_rejection_without_a_reason_adds_no_message(monkeypatch) -> None:
    graph = graph_with_replies(
        monkeypatch,
        [AIMessage(DRAFT_ONE), save_call(VALID_ARGS), AIMessage("What should change?")],
    )
    first = chat_service.send_message(graph, 1, None, "I need a backend engineer")
    chat_service.send_message(graph, 1, first.thread_id, "I approve this.")

    view = chat_service.submit_approval(graph, 1, first.thread_id, False, None, None)

    users = [item.text for item in view.items if item.kind == "user"]
    assert users == ["I need a backend engineer", "I approve this."]
