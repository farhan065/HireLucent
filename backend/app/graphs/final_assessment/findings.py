"""Evidence gaps and areas to verify, worked out by rule from the Q&A
analysis. No AI call, so they are always complete and correct.

- evidence gaps: job requirements the interview never explored
- areas to verify: things to check in a follow-up, namely a requirement the
  CV claims that the interview did not check, a question that was not
  answered, a company answer no reference could check, and a poor answer
  hidden behind a requirement's good average

Every finding points to its source: a transcript segment or the CV
screening result of a requirement. The same source shapes are used for the
strengths and weaknesses the AI writes (see report.py).
"""

from app.graphs.qa_analysis import coverage as coverage_rules

PRIORITY_WORDS = {"must_have": "must-have", "preferred": "preferred"}
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


def evidence_gaps(coverage: list[dict]) -> list[dict]:
    """The requirements no question touched, must-haves first."""
    missing = [entry for entry in coverage if entry["status"] == coverage_rules.NOT_EXPLORED]
    missing.sort(key=lambda entry: entry["priority"] != "must_have")
    return _numbered(
        "G",
        [
            (
                f"{entry['requirement_id']} {entry['text']} "
                f"({PRIORITY_WORDS.get(entry['priority'], entry['priority'])}) "
                "was not explored in the interview.",
                [cv_source(entry)],
            )
            for entry in missing
        ],
    )


def _lowest_pair(entry: dict, pairs_by_id: dict[str, dict]) -> dict | None:
    lowest = min(entry["question_scores"], key=lambda item: item["score"], default=None)
    return pairs_by_id.get(lowest["pair_id"]) if lowest else None


def areas_to_verify(pairs: list[dict], coverage: list[dict]) -> list[dict]:
    """What to check in a follow-up, each with its source."""
    pairs_by_id = {pair["id"]: pair for pair in pairs}
    found: list[tuple[str, list[dict]]] = []
    if not any(pair.get("evaluation") for pair in pairs):
        found.append((NO_JOB_QUESTIONS, []))

    for entry in coverage:
        cv_status = (entry.get("cv") or {}).get("status")
        name = f"{entry['requirement_id']} {entry['text']}"
        if entry["status"] == coverage_rules.NOT_EXPLORED and cv_status in (
            "met",
            "partially_met",
        ):
            found.append(
                (
                    f"Ask about {name}: the CV claims it, but the interview did not check it.",
                    [cv_source(entry)],
                )
            )
        elif entry["mixed"] and (pair := _lowest_pair(entry, pairs_by_id)):
            found.append(
                (
                    f"Probe {name} further: one of its answers scored below "
                    f"{coverage_rules.LOW_ANSWER_SCORE}.",
                    [transcript_source(pair)],
                )
            )

    for pair in pairs:
        evaluation = pair.get("evaluation")
        if not evaluation:
            continue
        if evaluation["answered"] == "not_answered":
            found.append(
                (
                    f"Ask again: “{pair['question']}” was not answered.",
                    [transcript_source(pair)],
                )
            )
        elif (evaluation.get("accuracy_source") or {}).get("type") == "not_checked":
            found.append(
                (
                    f"Check the answer to “{pair['question']}”: no company reference "
                    "covers it, so its accuracy was not checked.",
                    [transcript_source(pair)],
                )
            )
    return _numbered("V", found)
