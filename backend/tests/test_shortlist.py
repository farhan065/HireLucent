"""Tests for the shortlist rule the interviewer sends."""

import pytest
from pydantic import ValidationError

from app.schemas.candidate import ShortlistRule


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
