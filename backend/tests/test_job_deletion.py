"""Tests for deleting a job while it still has interviews."""

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
