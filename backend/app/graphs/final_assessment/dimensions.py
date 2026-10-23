"""The interview performance score (F9): six dimensions, each 0 to 100, and
the score made from them. Rule-based, no AI call.

Every dimension is an average of what LangGraph 3 already judged, so each
one points to the answers (or requirements) it rests on:

- technical: accuracy and completeness of each technical answer (a technical
  question not answered counts as 0)
- communication: articulation of each answered question
- relevance: relevance of each evaluated question (not answered counts as 0)
- problem_solving: the answers that showed problem-solving
- depth: the answers that described the candidate's own work
- alignment: the requirement coverage of the explored requirements, a
  must-have counting twice

A dimension with nothing to judge is "not assessed" (score None) and left
out, never scored 0: a candidate is not marked down for a question that was
never asked. The interview score is the average of the assessed dimensions,
each counting equally, and needs at least MIN_ASSESSED of them; with fewer
there is not enough interview evidence for a score.

Interviews evaluated before F9 have no problem-solving or depth judgements.
For them dimensions() returns None and the interview score stays the plain
average of the answers (see scoring.interview_score).
"""

from app.graphs.final_assessment import scoring
from app.graphs.qa_analysis import coverage as coverage_rules
from app.graphs.qa_analysis.evaluation import SHOWN_CRITERIA

# The dimensions, in the order shown.
TECHNICAL = "technical"
COMMUNICATION = "communication"
RELEVANCE = "relevance"
PROBLEM_SOLVING = "problem_solving"
DEPTH = "depth"
ALIGNMENT = "alignment"
ORDER = (TECHNICAL, COMMUNICATION, RELEVANCE, PROBLEM_SOLVING, DEPTH, ALIGNMENT)

NAMES = {
    TECHNICAL: "Technical competency",
    COMMUNICATION: "Communication",
    RELEVANCE: "Relevance of responses",
    PROBLEM_SOLVING: "Problem-solving approach",
    DEPTH: "Depth of experience",
    ALIGNMENT: "Alignment with job requirements",
}

# Fewer assessed dimensions than this give no interview score.
MIN_ASSESSED = 3
# How much a requirement counts in alignment, by priority.
PRIORITY_WEIGHTS = {"must_have": 2, "preferred": 1}

SCORED = "scored"
NOT_ENOUGH = "not_enough"


def _average(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def _not_answered(evaluation: dict) -> bool:
    return evaluation["answered"] == "not_answered"


def _answer(pair: dict, score: float, reason: str | None, evidence: dict | None) -> dict:
    """One answer a dimension rests on, as shown under it."""
    return {
        "pair_id": pair["id"],
        "question": pair["question"],
        "kind": pair["kind"],
        "score": round(score, 1),
        "reason": reason,
        "quote": evidence["quote"] if evidence else None,
        "turn_id": evidence["turn_id"] if evidence else None,
        "start_ms": evidence["start_ms"] if evidence else pair["start_ms"],
    }


def _criterion(evaluation: dict, name: str) -> dict | None:
    return (evaluation.get("criteria") or {}).get(name)


def _technical(pairs: list[dict]) -> list[dict]:
    answers = []
    for pair in pairs:
        if pair["kind"] != "technical":
            continue
        evaluation = pair["evaluation"]
        if _not_answered(evaluation):
            answers.append(_answer(pair, 0.0, evaluation["justification"], None))
            continue
        parts = [
            criterion["score"]
            for criterion in (
                _criterion(evaluation, "accuracy"),
                _criterion(evaluation, "completeness"),
            )
            if criterion
        ]
        if parts:
            answers.append(
                _answer(
                    pair,
                    sum(parts) / len(parts),
                    evaluation["justification"],
                    evaluation.get("evidence"),
                )
            )
    return answers


def _from_criterion(pairs: list[dict], name: str, unanswered_as_zero: bool) -> list[dict]:
    """Each evaluated answer's score for one of the four answer criteria."""
    answers = []
    for pair in pairs:
        evaluation = pair["evaluation"]
        if _not_answered(evaluation):
            if unanswered_as_zero:
                answers.append(_answer(pair, 0.0, evaluation["justification"], None))
            continue
        criterion = _criterion(evaluation, name)
        if criterion:
            answers.append(
                _answer(pair, criterion["score"], criterion["reason"], evaluation.get("evidence"))
            )
    return answers


def _shown(pairs: list[dict], name: str) -> list[dict]:
    """The answers that showed problem-solving, or the candidate's own work."""
    answers = []
    for pair in pairs:
        shown = pair["evaluation"].get(name)
        if shown:
            answers.append(_answer(pair, shown["score"], shown["reason"], shown["evidence"]))
    return answers


def _alignment(coverage: list[dict]) -> tuple[float | None, list[dict], list[str]]:
    explored = [
        entry
        for entry in coverage
        if entry["status"] != coverage_rules.NOT_EXPLORED and entry["average"] is not None
    ]
    weights = [PRIORITY_WEIGHTS.get(entry["priority"], 1) for entry in explored]
    score = None
    if explored:
        total = sum(entry["average"] * weight for entry, weight in zip(explored, weights))
        score = round(total / sum(weights), 1)
    requirements = [
        {
            "requirement_id": entry["requirement_id"],
            "text": entry["text"],
            "priority": entry["priority"],
            "status": entry["status"],
            "average": entry["average"],
        }
        for entry in explored
    ]
    not_explored = [
        entry["requirement_id"]
        for entry in coverage
        if entry["status"] == coverage_rules.NOT_EXPLORED
    ]
    return score, requirements, not_explored


def _count(number: int, word: str) -> str:
    return f"{number} {word}" if number == 1 else f"{number} {word}s"


def _based_on(key: str, answers: list[dict], coverage: list[dict]) -> str:
    """What the dimension rests on, in words, for the screen and the PDF."""
    if key == TECHNICAL:
        if not answers:
            return "No technical question was asked."
        return f"Accuracy and completeness of {_count(len(answers), 'technical answer')}"
    if key == COMMUNICATION:
        return f"Clarity of {_count(len(answers), 'answer')}" if answers else "No answer to judge."
    if key == RELEVANCE:
        if not answers:
            return "No job-related question was asked."
        return _count(len(answers), "question") + " asked"
    if key == PROBLEM_SOLVING:
        if not answers:
            return "No answer showed problem-solving."
        return f"{_count(len(answers), 'answer')} showed it"
    if key == DEPTH:
        if not answers:
            return "No answer described the candidate's own work."
        return f"{_count(len(answers), 'answer')} showed it"
    explored = sum(1 for entry in coverage if entry["status"] != coverage_rules.NOT_EXPLORED)
    if not explored:
        return "No job requirement was explored."
    return f"{explored} of {len(coverage)} requirements explored · must-haves count double"


def is_scored_by_dimensions(pairs: list[dict]) -> bool:
    """True when the answers were judged with problem-solving and depth (F9).
    An interview evaluated before F9 keeps its plain answer average."""
    evaluated = scoring.evaluated(pairs)
    return bool(evaluated) and all(
        all(name in pair["evaluation"] for name in SHOWN_CRITERIA) for pair in evaluated
    )


def dimensions(pairs: list[dict], coverage: list[dict]) -> dict | None:
    """The six dimensions and the interview score made from them, or None
    for an interview evaluated before F9 (see the module docstring)."""
    evaluated = scoring.evaluated(pairs)
    if evaluated and not is_scored_by_dimensions(pairs):
        return None
    answers_by_key = {
        TECHNICAL: _technical(evaluated),
        COMMUNICATION: _from_criterion(evaluated, "articulation", unanswered_as_zero=False),
        RELEVANCE: _from_criterion(evaluated, "relevance", unanswered_as_zero=True),
        PROBLEM_SOLVING: _shown(evaluated, PROBLEM_SOLVING),
        DEPTH: _shown(evaluated, DEPTH),
    }
    alignment, requirements, not_explored = _alignment(coverage)
    items = []
    for key in ORDER:
        answers = answers_by_key.get(key, [])
        score = alignment if key == ALIGNMENT else _average([a["score"] for a in answers])
        items.append(
            {
                "key": key,
                "name": NAMES[key],
                "score": score,
                "based_on": _based_on(key, answers, coverage),
                "answers": answers,
                "requirements": requirements if key == ALIGNMENT else [],
                "not_explored": not_explored if key == ALIGNMENT else [],
            }
        )
    assessed = [item["score"] for item in items if item["score"] is not None]
    enough = len(assessed) >= MIN_ASSESSED
    return {
        "status": SCORED if enough else NOT_ENOUGH,
        "score": _average(assessed) if enough else None,
        "assessed": len(assessed),
        "total": len(ORDER),
        "min_assessed": MIN_ASSESSED,
        "dimensions": items,
    }


def interview_score(pairs: list[dict], scored: dict | None) -> float | None:
    """The interview score: from the dimensions when they exist, else the
    plain answer average of an interview evaluated before F9."""
    if scored is None:
        return scoring.interview_score(pairs)
    return scored["score"]
