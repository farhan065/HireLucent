"""Requirement coverage: which job requirements the interview explored, and
how well the candidate answered on each. Rule-based, no AI call.

Each pair was tagged with the requirements it explores during segmentation.
For every requirement of the job, the evaluated pairs that explored it are
collected with their answer scores:

- covered: the average answer score is COVERED_SCORE or more
- weak: it was explored, but the average is below COVERED_SCORE
- not_explored: no question touched it

A covered requirement with one answer below LOW_ANSWER_SCORE is marked
"mixed", so a poor answer is not hidden by a good average. The CV screening
result for the requirement is shown next to it, so a requirement the CV
claims but the interview never checked stands out.
"""

# The average answer score at which a requirement counts as covered.
COVERED_SCORE = 60
# An answer below this makes a covered requirement "mixed".
LOW_ANSWER_SCORE = 40

COVERED = "covered"
WEAK = "weak"
NOT_EXPLORED = "not_explored"


def _cv_result(match: dict | None) -> dict | None:
    """What CV screening found for the requirement, if it was screened."""
    if match is None:
        return None
    return {"status": match["status"], "evidence": match.get("evidence", "")}


def map_coverage(
    pairs: list[dict], requirements: list[dict], cv_matches: list[dict] | None
) -> list[dict]:
    """One entry per job requirement, in the job's order."""
    cv_by_id = {match["id"]: match for match in cv_matches or []}
    coverage = []
    for item in requirements:
        scores = [
            {"pair_id": pair["id"], "score": pair["evaluation"]["score"]}
            for pair in pairs
            if item["id"] in pair.get("requirement_ids", []) and pair.get("evaluation")
        ]
        values = [entry["score"] for entry in scores]
        average = round(sum(values) / len(values), 1) if values else None
        if average is None:
            status = NOT_EXPLORED
        elif average >= COVERED_SCORE:
            status = COVERED
        else:
            status = WEAK
        coverage.append(
            {
                "requirement_id": item["id"],
                "text": item["text"],
                "priority": item["priority"],
                "status": status,
                "average": average,
                "question_scores": scores,
                "mixed": status == COVERED and min(values) < LOW_ANSWER_SCORE,
                "cv": _cv_result(cv_by_id.get(item["id"])),
            }
        )
    return coverage


def counts(coverage: list[dict]) -> dict[str, int]:
    """How many requirements have each status, for the logs."""
    statuses = [entry["status"] for entry in coverage]
    return {
        "covered": statuses.count(COVERED),
        "weak": statuses.count(WEAK),
        "not_explored": statuses.count(NOT_EXPLORED),
    }
