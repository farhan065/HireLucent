"""Evidence gaps and areas to verify, worked out by rule from the Q&A
analysis. No AI call, so they are always complete and correct.

- evidence gaps: job requirements the interview never explored, each with
  what the CV says about it
- areas to verify: things to double-check before deciding, about questions
  that were asked: one that was not answered, a poor answer hidden behind a
  requirement's good average, or an answer whose accuracy could not be
  checked

Each fact appears once: a requirement that was not explored is only an
evidence gap, and a question is listed at most once, for its most important
reason.

Every finding points to its source: a transcript segment or the CV
screening result of a requirement. The same source shapes are used for the
strengths and weaknesses the AI writes (see report.py).
"""

from app.graphs.qa_analysis import coverage as coverage_rules

PRIORITY_WORDS = {"must_have": "must-have", "preferred": "preferred"}
CV_WORDS = {
    "met": "the CV meets it",
    "partially_met": "the CV partly meets it",
    "unmet": "the CV does not meet it",
}
NO_JOB_QUESTIONS = "No job-related questions were found in this interview."


def transcript_source(pair: dict, turn: dict | None = None, quote: str | None = None) -> dict:
    """A transcript segment: the question, the turn and the quote. Without a
    given turn, the evaluation's own evidence is used, or else the turn that
    asked the question."""
    evidence = (pair.get("evaluation") or {}).get("evidence")
    if turn is not None:
        turn_id, start_ms = turn["id"], turn["start_ms"]
    elif evidence:
        turn_id, start_ms, quote = evidence["turn_id"], evidence["start_ms"], evidence["quote"]
    else:
        turn_id, start_ms = pair["question_turn_ids"][0], pair["start_ms"]
    return {
        "type": "transcript",
        "pair_id": pair["id"],
        "question": pair["question"],
        "turn_id": turn_id,
        "start_ms": start_ms,
        "quote": quote,
    }


def cv_source(entry: dict) -> dict:
    """A requirement with what CV screening found for it, if it was
    screened."""
    cv = entry.get("cv") or {}
    return {
        "type": "cv",
        "requirement_id": entry["requirement_id"],
        "requirement": entry["text"],
        "status": cv.get("status"),
        "evidence": cv.get("evidence") or None,
    }


def _numbered(prefix: str, findings: list[tuple[str, list[dict]]]) -> list[dict]:
    return [
        {"id": f"{prefix}{number}", "text": text, "sources": sources}
        for number, (text, sources) in enumerate(findings, start=1)
    ]


def _name(entry: dict) -> str:
    """The requirement's id and text, without a closing full stop."""
    return f"{entry['requirement_id']} {entry['text'].strip().rstrip('.')}"


def evidence_gaps(coverage: list[dict]) -> list[dict]:
    """The requirements no question touched, must-haves first, each with
    what CV screening found for it."""
    missing = [entry for entry in coverage if entry["status"] == coverage_rules.NOT_EXPLORED]
    missing.sort(key=lambda entry: entry["priority"] != "must_have")
    found = []
    for entry in missing:
        cv_status = (entry.get("cv") or {}).get("status")
        cv = CV_WORDS.get(cv_status, "the CV was not screened for it")
        found.append(
            (
                f"{_name(entry)} ({PRIORITY_WORDS.get(entry['priority'], entry['priority'])}) "
                f"was not explored in the interview; {cv}.",
                [cv_source(entry)],
            )
        )
    return _numbered("G", found)


def _lowest_pair(entry: dict, pairs_by_id: dict[str, dict]) -> dict | None:
    lowest = min(entry["question_scores"], key=lambda item: item["score"], default=None)
    return pairs_by_id.get(lowest["pair_id"]) if lowest else None


def _requirement_ids(pair: dict) -> str:
    """The requirements the question explores, as a short note, or ""."""
    ids = pair.get("requirement_ids") or []
    if not ids:
        return ""
    word = "requirement" if len(ids) == 1 else "requirements"
    return f" ({word} {', '.join(ids)})"


def areas_to_verify(pairs: list[dict], coverage: list[dict]) -> list[dict]:
    """What to double-check before deciding, one line per question asked,
    each with its source. Requirements that were never explored are the
    evidence gaps, so they are not repeated here."""
    pairs_by_id = {pair["id"]: pair for pair in pairs}
    if not any(pair.get("evaluation") for pair in pairs):
        return _numbered("V", [(NO_JOB_QUESTIONS, [])])

    # The poor answer behind each mixed requirement, by question.
    mixed: dict[str, list[str]] = {}
    for entry in coverage:
        if entry["mixed"] and (pair := _lowest_pair(entry, pairs_by_id)):
            mixed.setdefault(pair["id"], []).append(entry["requirement_id"])

    found: list[tuple[str, list[dict]]] = []
    for pair in pairs:
        evaluation = pair.get("evaluation")
        if not evaluation:
            continue
        asked = f"{pair['id']} “{pair['question'].strip()}”"
        if evaluation["answered"] == "not_answered":
            text = f"{asked} was not answered{_requirement_ids(pair)}."
        elif pair["id"] in mixed:
            ids = ", ".join(mixed[pair["id"]])
            text = (
                f"{asked} scored below {coverage_rules.LOW_ANSWER_SCORE}, though {ids} "
                "looks covered on average."
            )
        elif (evaluation.get("accuracy_source") or {}).get("type") == "not_checked":
            reason = (
                "no company reference covers it"
                if pair["kind"] == "company"
                else "the AI could not judge it"
            )
            text = f"{asked}: the accuracy was not checked, because {reason}."
        else:
            continue
        found.append((text, [transcript_source(pair)]))
    return _numbered("V", found)
