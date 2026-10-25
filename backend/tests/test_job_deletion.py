"""Tests for deleting a job or a candidate: open interviews block a job's
deletion, and nothing of a deleted candidate is left in the saved LangGraph
state (BID privacy: deletion and data minimisation)."""

from fnmatch import fnmatchcase
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.errors import ConflictError
from app.services import job_deletion, session_service


class FakeDB:
    def __init__(self, count: int = 0):
        self.count = count
        self.deleted = []

    def scalar(self, query):
        return self.count

    def delete(self, item):
        self.deleted.append(item)


@pytest.fixture()
def job_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(job_deletion.job_service, "get_job", lambda db, job_id: object())
    monkeypatch.setattr(job_deletion.task_service, "ensure_idle", lambda db, job_id: None)


def test_a_job_with_an_upcoming_interview_is_not_deleted(job_found) -> None:
    db = FakeDB(count=1)

    with pytest.raises(ConflictError, match="Cancel them on the Interviews tab"):
        job_deletion.delete_job(db, 2)

    assert db.deleted == []


def test_open_interviews_are_counted_for_the_job() -> None:
    assert session_service.has_open_interviews(FakeDB(count=1), 2) is True
    assert session_service.has_open_interviews(FakeDB(count=0), 2) is False


# --- Saved LangGraph state ---------------------------------------------------


class FakeConnection:
    """Answers the search for a thread name the way PostgreSQL's LIKE does."""

    def __init__(self, saved: set[str]) -> None:
        self.saved = saved

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None

    def execute(self, query: str, params: dict):
        pattern = params["p"].replace("%", "*")
        found = [{"thread_id": t} for t in sorted(self.saved) if fnmatchcase(t, pattern)]
        return SimpleNamespace(fetchall=lambda: found)


class FakeCheckpointer:
    """The checkpoint tables, holding a set of thread names."""

    def __init__(self, saved: set[str]) -> None:
        self.saved = set(saved)
        self.conn = SimpleNamespace(connection=lambda: FakeConnection(self.saved))

    def delete_thread(self, thread_id: str) -> None:
        self.saved.discard(thread_id)


class DeletionDB:
    """Hands out the ids each query asks for, in the order they are asked."""

    def __init__(self, answers: list[list], candidate=None) -> None:
        self.answers = list(answers)
        self.candidate = candidate
        self.deleted = []

    def scalars(self, query):
        return iter(self.answers.pop(0))

    def scalar(self, query):
        return 0  # no open interviews

    def get(self, model, item_id):
        return self.candidate

    def add(self, item) -> None:
        pass

    def delete(self, item) -> None:
        self.deleted.append(item)

    def execute(self, query) -> None:
        pass

    def commit(self) -> None:
        pass


def interview_threads(session_id: int) -> set[str]:
    """Every thread one interview can leave behind."""
    return {
        f"interview-{session_id}",
        f"final-assessment-{session_id}",
        f"cv-claims-{session_id}",
        f"interview-quality-{session_id}",
        f"evaluation-3f2a9c-{session_id}",
        f"evaluation-71bd04-{session_id}",
    }


@pytest.fixture()
def nothing_outside(monkeypatch: pytest.MonkeyPatch) -> None:
    """The vector store, the CV folder and the ranking are left alone."""
    monkeypatch.setattr(job_deletion, "_delete_cv_vectors", lambda where: None)
    monkeypatch.setattr(job_deletion.screening_store, "rerank", lambda job_id: None)
    monkeypatch.setattr(job_deletion.shutil, "rmtree", lambda path, ignore_errors: None)
    monkeypatch.setattr(job_deletion.task_service, "ensure_idle", lambda db, job_id: None)


def use_checkpoints(monkeypatch: pytest.MonkeyPatch, saved: set[str]) -> FakeCheckpointer:
    checkpointer = FakeCheckpointer(saved)
    monkeypatch.setattr(job_deletion, "get_checkpointer", lambda: checkpointer)
    return checkpointer


def test_deleting_a_candidate_deletes_all_their_saved_ai_work(
    monkeypatch: pytest.MonkeyPatch, nothing_outside, tmp_path: Path
) -> None:
    # Candidate 3 had interviews 7 and 8. Interviews 17 and 70 belong to
    # another candidate: their ids end in the same digit but must stay.
    others = interview_threads(17) | interview_threads(70) | {"feedback-4"}
    checkpointer = use_checkpoints(
        monkeypatch, interview_threads(7) | interview_threads(8) | {"feedback-3"} | others
    )
    candidate = SimpleNamespace(
        job_id=2, source_ref=None, cv_path=str(tmp_path / "cv.pdf"), photo_path=None
    )

    job_deletion.delete_candidate(DeletionDB([[7, 8]], candidate), 3)

    assert checkpointer.saved == others


def test_deleting_a_candidate_without_interviews_deletes_their_feedback_state(
    monkeypatch: pytest.MonkeyPatch, nothing_outside, tmp_path: Path
) -> None:
    checkpointer = use_checkpoints(monkeypatch, {"feedback-3", "feedback-4"})
    candidate = SimpleNamespace(
        job_id=2, source_ref=None, cv_path=str(tmp_path / "cv.pdf"), photo_path=None
    )

    job_deletion.delete_candidate(DeletionDB([[]], candidate), 3)

    assert checkpointer.saved == {"feedback-4"}


def test_deleting_a_job_deletes_the_saved_ai_work_of_all_its_interviews(
    monkeypatch: pytest.MonkeyPatch, job_found, nothing_outside
) -> None:
    # Job 2: conversation "job-chat", screening task "s1", interviews 7 and 8,
    # candidates 3 and 5. Interview 9 belongs to another job.
    others = interview_threads(9) | {"feedback-6", "other-chat"}
    checkpointer = use_checkpoints(
        monkeypatch,
        interview_threads(7)
        | interview_threads(8)
        | {"job-chat", "screening-s1", "feedback-3", "feedback-5"}
        | others,
    )
    monkeypatch.setattr(
        job_deletion.screening_service, "thread_id", lambda task_id: f"screening-{task_id}"
    )

    job_deletion.delete_job(DeletionDB([["job-chat"], ["s1"], [7, 8], [3, 5]]), 2)

    assert checkpointer.saved == others


class OpenInterviewDB(DeletionDB):
    """A candidate who still has a scheduled interview."""

    def scalar(self, query):
        return 1


def test_a_candidate_with_an_upcoming_interview_is_not_deleted(
    monkeypatch: pytest.MonkeyPatch, nothing_outside, tmp_path: Path
) -> None:
    checkpointer = use_checkpoints(monkeypatch, interview_threads(7) | {"feedback-3"})
    candidate = SimpleNamespace(
        job_id=2, source_ref=None, cv_path=str(tmp_path / "cv.pdf"), photo_path=None
    )
    db = OpenInterviewDB([[7]], candidate)

    with pytest.raises(ConflictError, match="Cancel it on the Interviews tab"):
        job_deletion.delete_candidate(db, 3)

    assert db.deleted == []
    assert checkpointer.saved == interview_threads(7) | {"feedback-3"}


def test_open_interviews_are_counted_for_the_candidate() -> None:
    assert session_service.candidate_has_open_interview(FakeDB(count=1), 3) is True
    assert session_service.candidate_has_open_interview(FakeDB(count=0), 3) is False
