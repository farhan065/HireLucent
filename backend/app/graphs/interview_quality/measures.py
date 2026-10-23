"""Interview quality (F10): what code measures about how the interview was
run. No AI call.

Three parts, each 0-100, count equally in the quality score:

- questions: the share of job-related questions that gave a useful answer.
  A question gives little signal when it was not answered, the answer was
  very short (under SHORT_ANSWER_WORDS words), or the answer was judged off
  the question (relevance below LOW_RELEVANCE). A technical or behavioural
  question linked to no job requirement does not count as useful either.
  Small talk is left out.
- coverage: how well the job's requirements were explored. Covered counts
  1, weak 1/2, not explored 0, and a must-have counts double.
- interaction: starts at 100 and loses points when the candidate spoke
  less than BALANCED_SHARE_MIN of the time (2 per point below, at most 40),
  when small talk took over SMALL_TALK_MAX of the time (1 per point over, at
  most 20), for each minute an interviewer stretch ran over
  STRETCH_MAX_MS (10 a minute, at most 20) and when the interview lasted
  under half its planned length (20).

Label: good from 70, needs improvement from 50, otherwise poor. The result
is about the interview, never the candidate: it changes no score of the
candidate, the report or the decision.

Each finding is a plain fact with the questions, requirements or times it
rests on, so the recommendations written from it can be checked.
"""

from statistics import median

from app.graphs.qa_analysis import coverage as coverage_rules
from app.graphs.qa_analysis.segmentation import EVALUATED_KINDS

SHORT_ANSWER_WORDS = 5
LOW_RELEVANCE = 40
# The candidate's share of the speaking time that counts as balanced.
BALANCED_SHARE_MIN = 60
BALANCED_SHARE_MAX = 70
SMALL_TALK_MAX = 20
STRETCH_MAX_MS = 120_000
# Kinds of question that should explore a job requirement.
LINKED_KINDS = ("technical", "behavioural")

GOOD = "good"
NEEDS_IMPROVEMENT = "needs_improvement"
POOR = "poor"
GOOD_FROM = 70
NEEDS_IMPROVEMENT_FROM = 50

STATUS_WEIGHT = {coverage_rules.COVERED: 1.0, coverage_rules.WEAK: 0.5}
PRIORITY_WEIGHT = {"must_have": 2, "preferred": 1}
PRIORITY_LABEL = {"must_have": "must-have", "preferred": "preferred"}
# Segments closer than this are drawn as one on the timeline.
JOIN_GAP_MS = 1_000
MAX_SEGMENTS = 400


def clock(ms: int | None) -> str:
    """A time from the interview's start, as mm:ss."""
    seconds = max(int((ms or 0) // 1000), 0)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def duration(ms: int) -> str:
    """A length, as m:ss."""
    seconds = max(int(round(ms / 1000)), 0)
    return f"{seconds // 60}:{seconds % 60:02d}"


def _round(value: float) -> float:
    return round(value, 1)


def job_questions(pairs: list[dict]) -> list[dict]:
    return [pair for pair in pairs if pair.get("kind") in EVALUATED_KINDS]


def answer_words(pair: dict, turns: dict[int, dict]) -> int:
    return sum(
        turns[turn_id]["words"] for turn_id in pair.get("answer_turn_ids", []) if turn_id in turns
    )


def little_signal_reason(pair: dict, turns: dict[int, dict]) -> str | None:
    """Why the question gave little signal, or None when it gave a useful
    answer."""
    evaluation = pair.get("evaluation") or {}
    if evaluation.get("answered") == "not_answered" or not pair.get("answer_turn_ids"):
        return "not answered"
    words = answer_words(pair, turns)
    if words < SHORT_ANSWER_WORDS:
        return f"{words}-word answer" if words != 1 else "1-word answer"
    relevance = ((evaluation.get("criteria") or {}).get("relevance") or {}).get("score")
    if relevance is not None and relevance < LOW_RELEVANCE:
        return "answer off the question"
    return None


# --- Measured from the transcript ---------------------------------------------


def _segments(turns: list[dict]) -> list[dict]:
    """Who spoke when, joining a speaker's turns that follow within a second.
    Each segment keeps its first turn, so the screens can open the
    transcript there."""
    segments: list[dict] = []
    last: dict[str, dict] = {}
    for turn in sorted(turns, key=lambda item: (item["start_ms"], item["id"])):
        previous = last.get(turn["speaker"])
        if previous is not None and turn["start_ms"] - previous["end_ms"] <= JOIN_GAP_MS:
            previous["end_ms"] = max(previous["end_ms"], turn["end_ms"])
            continue
        segment = {
            "speaker": turn["speaker"],
            "start_ms": turn["start_ms"],
            "end_ms": turn["end_ms"],
            "turn_id": turn["id"],
        }
        segments.append(segment)
        last[turn["speaker"]] = segment
    return segments[:MAX_SEGMENTS]


def _longest_stretch(turns: list[dict]) -> dict | None:
    """The interviewer's longest run of speech with no candidate turn
    starting in it."""
    best = None
    run = None
    for turn in sorted(turns, key=lambda item: (item["start_ms"], item["id"])):
        if turn["speaker"] == "interviewer":
            if run is None:
                run = {"start_ms": turn["start_ms"], "end_ms": turn["end_ms"]}
            else:
                run["end_ms"] = max(run["end_ms"], turn["end_ms"])
        else:
            run = None
        if run is not None:
            length = run["end_ms"] - run["start_ms"]
            if best is None or length > best["ms"]:
                best = {"ms": length, "start_ms": run["start_ms"]}
    return best


def _spoken(turns: list[dict], speaker: str) -> int:
    return sum(
        max(turn["end_ms"] - turn["start_ms"], 0) for turn in turns if turn["speaker"] == speaker
    )


def measure(
    pairs: list[dict], turns: list[dict], planned_ms: int | None, actual_ms: int | None
) -> dict:
    """The interview's numbers: speaking time per speaker, the longest
    interviewer stretch, small talk, follow-ups, questions by kind and the
    length against the planned length."""
    by_id = {turn["id"]: turn for turn in turns}
    interviewer = _spoken(turns, "interviewer")
    candidate = _spoken(turns, "candidate")
    total = interviewer + candidate
    small_talk_turns = {
        turn_id
        for pair in pairs
        if pair.get("kind") == "small_talk"
        for turn_id in [*pair.get("question_turn_ids", []), *pair.get("answer_turn_ids", [])]
    }
    small_talk = sum(
        max(by_id[turn_id]["end_ms"] - by_id[turn_id]["start_ms"], 0)
        for turn_id in small_talk_turns
        if turn_id in by_id
    )
    kinds: dict[str, int] = {}
    for pair in pairs:
        kinds[pair.get("kind", "")] = kinds.get(pair.get("kind", ""), 0) + 1
    length = (
        actual_ms if actual_ms else (max((turn["end_ms"] for turn in turns), default=0) or None)
    )
    return {
        "interviewer_ms": interviewer,
        "candidate_ms": candidate,
        "candidate_share": _round(100 * candidate / total) if total else None,
        "longest_stretch": _longest_stretch(turns),
        "small_talk_ms": small_talk,
        "small_talk_share": _round(100 * small_talk / total) if total else None,
        "small_talk_questions": kinds.get("small_talk", 0),
        "follow_ups": [pair["follow_up_of"] for pair in pairs if pair.get("follow_up_of")],
        "questions_by_kind": {kind: count for kind, count in kinds.items() if kind},
        "job_questions": len(job_questions(pairs)),
        "planned_minutes": round(planned_ms / 60_000) if planned_ms else None,
        "actual_minutes": round(length / 60_000) if length else None,
        "actual_ms": length,
        "planned_ms": planned_ms,
        "segments": _segments(turns),
    }


# --- The three parts -----------------------------------------------------------


def questions_part(pairs: list[dict], turns: dict[int, dict]) -> dict:
    asked = job_questions(pairs)
    little_signal, not_linked = [], []
    for pair in asked:
        reason = little_signal_reason(pair, turns)
        if reason:
            little_signal.append({"id": pair["id"], "reason": reason})
        elif pair["kind"] in LINKED_KINDS and not pair.get("requirement_ids"):
            not_linked.append({"id": pair["id"]})
    useful = len(asked) - len(little_signal) - len(not_linked)
    return {
        "score": _round(100 * useful / len(asked)) if asked else 0.0,
        "useful": useful,
        "total": len(asked),
        "little_signal": little_signal,
        "not_linked": not_linked,
    }


def coverage_part(coverage: list[dict]) -> dict | None:
    if not coverage:
        return None
    points = sum(
        STATUS_WEIGHT.get(entry["status"], 0) * PRIORITY_WEIGHT.get(entry["priority"], 1)
        for entry in coverage
    )
    most = sum(PRIORITY_WEIGHT.get(entry["priority"], 1) for entry in coverage)
    return {
        "score": _round(100 * points / most) if most else 0.0,
        "points": points,
        "max": most,
        "explored": sum(entry["status"] != coverage_rules.NOT_EXPLORED for entry in coverage),
        "total": len(coverage),
        "weak": [
            entry["requirement_id"] for entry in coverage if entry["status"] == coverage_rules.WEAK
        ],
        "missing": [
            entry["requirement_id"]
            for entry in coverage
            if entry["status"] == coverage_rules.NOT_EXPLORED
        ],
    }


def interaction_part(metrics: dict) -> dict | None:
    share = metrics["candidate_share"]
    if share is None:
        return None
    penalties = []
    below = max(BALANCED_SHARE_MIN - share, 0)
    penalties.append(
        {
            "key": "speaking_share",
            "label": f"Candidate spoke {share:g}%"
            + (f" ({below:g} below {BALANCED_SHARE_MIN})" if below else ""),
            "points": -_round(min(2 * below, 40)),
        }
    )
    small_talk = metrics["small_talk_share"] or 0
    over = max(small_talk - SMALL_TALK_MAX, 0)
    penalties.append(
        {
            "key": "small_talk",
            "label": f"Small talk {small_talk:g}%",
            "points": -_round(min(over, 20)),
        }
    )
    stretch = metrics["longest_stretch"]
    if stretch:
        extra_minutes = max(stretch["ms"] - STRETCH_MAX_MS, 0) / 60_000
        penalties.append(
            {
                "key": "long_stretch",
                "label": f"Longest stretch {duration(stretch['ms'])}",
                "points": -_round(min(10 * extra_minutes, 20)),
            }
        )
    planned, actual = metrics["planned_ms"], metrics["actual_ms"]
    if planned and actual:
        penalties.append(
            {
                "key": "short_interview",
                "label": f"Length {metrics['actual_minutes']} of {metrics['planned_minutes']} min",
                "points": -20.0 if actual < planned / 2 else 0.0,
            }
        )
    score = max(100 + sum(item["points"] for item in penalties), 0)
    return {"score": _round(score), "penalties": penalties}


def label(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= GOOD_FROM:
        return GOOD
    return NEEDS_IMPROVEMENT if score >= NEEDS_IMPROVEMENT_FROM else POOR


def score_parts(parts: dict) -> float | None:
    """The quality score: the average of the parts that could be worked out."""
    scores = [part["score"] for part in parts.values() if part is not None]
    return _round(sum(scores) / len(scores)) if scores else None


# --- Findings for the recommendations ------------------------------------------


def _question_ref(pair: dict, note: str) -> dict:
    return {
        "type": "question",
        "id": pair["id"],
        "start_ms": pair.get("start_ms"),
        "label": f"{pair['id']} · {clock(pair.get('start_ms'))} · {note}",
    }


def _requirement_ref(entry: dict) -> dict:
    status = entry["status"].replace("_", " ")
    priority = PRIORITY_LABEL.get(entry["priority"], entry["priority"])
    return {
        "type": "requirement",
        "id": entry["requirement_id"],
        "label": f"{entry['requirement_id']} · {priority} · {status}",
    }


def findings(pairs: list[dict], coverage: list[dict], metrics: dict, parts: dict) -> list[dict]:
    """Every problem found, each as a plain fact with what it rests on. Ids
    F1, F2, … in order: coverage first, then questions, then interaction."""
    found: list[dict] = []

    def add(kind: str, text: str, refs: list[dict]) -> None:
        found.append({"kind": kind, "text": text, "refs": refs})

    by_pair = {pair["id"]: pair for pair in pairs}
    asked = job_questions(pairs)
    if not asked:
        add("no_job_questions", "No job-related questions were asked.", [])
    elif not any(pair["kind"] == "technical" for pair in asked):
        add("no_technical", "No technical questions were asked.", [])

    must_first = sorted(coverage, key=lambda entry: entry["priority"] != "must_have")
    for entry in must_first:
        priority = PRIORITY_LABEL.get(entry["priority"], entry["priority"])
        if entry["status"] == coverage_rules.NOT_EXPLORED:
            add(
                "not_explored",
                f"{entry['requirement_id']} {entry['text']} ({priority}) was never explored "
                "by any question.",
                [_requirement_ref(entry)],
            )
    for entry in must_first:
        priority = PRIORITY_LABEL.get(entry["priority"], entry["priority"])
        if entry["status"] == coverage_rules.WEAK:
            ids = [item["pair_id"] for item in entry.get("question_scores", [])]
            refs = [_requirement_ref(entry)] + [
                _question_ref(by_pair[pair_id], "weak answer")
                for pair_id in ids
                if pair_id in by_pair
            ]
            add(
                "weak",
                f"{entry['requirement_id']} {entry['text']} ({priority}) was explored only weakly "
                f"in {', '.join(ids)}: the answers averaged {entry['average']:g} of 100.",
                refs,
            )

    for item in parts["questions"]["little_signal"]:
        pair = by_pair[item["id"]]
        add(
            "little_signal",
            f'{pair["id"]} at {clock(pair.get("start_ms"))} ("{pair["question"]}") gave little '
            f"signal: {item['reason']}.",
            [_question_ref(pair, item["reason"])],
        )
    for item in parts["questions"]["not_linked"]:
        pair = by_pair[item["id"]]
        add(
            "not_linked",
            f'{pair["id"]} at {clock(pair.get("start_ms"))} ("{pair["question"]}") is a '
            f"{pair['kind']} question linked to no job requirement.",
            [_question_ref(pair, "no requirement")],
        )

    share = metrics["candidate_share"]
    if share is not None and share < BALANCED_SHARE_MIN:
        interviewer = _round(100 - share)
        add(
            "speaking_share",
            f"The candidate spoke {share:g}% of the time and the interviewer {interviewer:g}%. "
            f"Balanced is the candidate speaking {BALANCED_SHARE_MIN}-{BALANCED_SHARE_MAX}%.",
            [
                {
                    "type": "measure",
                    "label": f"Candidate {share:g}% · balanced "
                    f"{BALANCED_SHARE_MIN}–{BALANCED_SHARE_MAX}%",
                }
            ],
        )
    stretch = metrics["longest_stretch"]
    if stretch and stretch["ms"] > STRETCH_MAX_MS:
        add(
            "long_stretch",
            f"The interviewer spoke for {duration(stretch['ms'])} without a break at "
            f"{clock(stretch['start_ms'])}, over the 2-minute mark.",
            [
                {
                    "type": "time",
                    "start_ms": stretch["start_ms"],
                    "label": f"{clock(stretch['start_ms'])} · {duration(stretch['ms'])} stretch",
                }
            ],
        )
    small_talk = metrics["small_talk_share"]
    if small_talk is not None and small_talk > SMALL_TALK_MAX:
        add(
            "small_talk",
            f"Small talk took {small_talk:g}% of the speaking time, over {SMALL_TALK_MAX}%.",
            [{"type": "measure", "label": f"Small talk {small_talk:g}%"}],
        )
    planned, actual = metrics["planned_ms"], metrics["actual_ms"]
    if planned and actual and actual < planned / 2:
        add(
            "short_interview",
            f"The interview lasted {metrics['actual_minutes']} of {metrics['planned_minutes']} "
            "planned minutes, under half.",
            [
                {
                    "type": "measure",
                    "label": f"{metrics['actual_minutes']} of {metrics['planned_minutes']} min",
                }
            ],
        )
    for number, finding in enumerate(found, start=1):
        finding["id"] = f"F{number}"
    return found


def explored_requirements(coverage: list[dict]) -> list[str]:
    return [
        entry["requirement_id"]
        for entry in coverage
        if entry["status"] != coverage_rules.NOT_EXPLORED
    ]


def typical(values: list[float]) -> float | None:
    """The middle value, or None with no values."""
    values = [value for value in values if value is not None]
    return _round(median(values)) if values else None
