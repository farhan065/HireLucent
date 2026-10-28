"""Tests for the shortlist: the rule the interviewer sends and who can be
added or removed."""

import pytest
from pydantic import ValidationError

from app.core.errors import ConflictError
from app.models import Candidate
from app.models.enums import CandidateStatus
from app.schemas.candidate import ShortlistRule
from app.services import shortlist_service


@pytest.mark.parametrize("rule", [{"top": 3}, {"min_score": 70}])
def test_one_rule_is_accepted(rule: dict) -> None:
    ShortlistRule(**rule)


@pytest.mark.parametrize(
    "rule",
    [{}, {"top": 3, "min_score": 70}, {"top": 0}, {"min_score": 101}],
)
def test_no_rule_two_rules_or_an_out_of_range_value_is_rejected(rule: dict) -> None:
    with pytest.raises(ValidationError):
        ShortlistRule(**rule)


class FakeDB:
    def __init__(self, candidate):
        self.candidate = candidate

    def get(self, model, key):
        return self.candidate


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (CandidateStatus.INTERVIEW_SCHEDULED, "has an interview"),
        (CandidateStatus.EXCLUDED, "Only candidates with a final score"),
    ],
)
def test_shortlist_cannot_change_without_a_score_or_with_an_interview(
    status, message: str
) -> None:
    candidate = Candidate(id=5, job_id=2, full_name="Test", status=status)

    with pytest.raises(ConflictError, match=message):
        shortlist_service.set_shortlisted(FakeDB(candidate), 5, shortlisted=False)
    assert candidate.status == status
