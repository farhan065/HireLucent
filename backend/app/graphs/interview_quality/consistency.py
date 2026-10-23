"""Interview consistency (F10): were the candidates for one job interviewed
in a similar way? Code only, worked out when it is read from the job's
evaluated interviews that have an interview quality check, so it is never
out of date when another interview is evaluated.

The typical interview is the middle value (median) of the interviews'
length, number of job-related questions and the candidate's share of the
speaking time. An interview is flagged when:
- a must-have it did not explore was explored in most of the job's other
  interviews,
- its length or number of questions is under half or over 1.5 times the
  typical one,
- the candidate's share differs from the typical one by more than
  SHARE_DIFFERENCE points.
A requirement explored in fewer than half of the interviews is "mostly
missed" for the whole job. Shown once MIN_INTERVIEWS are checked.
"""

from app.graphs.interview_quality.measures import typical

MIN_INTERVIEWS = 2
SHARE_DIFFERENCE = 20
LOW_RATIO = 0.5
HIGH_RATIO = 1.5


def _off(value, middle) -> bool:
    return bool(
        value is not None and middle and not LOW_RATIO * middle <= value <= HIGH_RATIO * middle
    )


def interview_flags(
    row: dict, rows: list[dict], typical_values: dict, requirements: list[dict]
) -> list[dict]:
    """How one interview differs from the rest of the job's interviews."""
    flags: list[dict] = []
    others = [other for other in rows if other["session_id"] != row["session_id"]]
    for requirement in requirements:
        rid = requirement["id"]
        if requirement["priority"] != "must_have" or rid in row["explored"] or not others:
            continue
        asked = sum(rid in other["explored"] for other in others)
        if asked * 2 > len(others):
            flags.append(
                {
                    "kind": "must_have_not_asked",
                    "requirement_id": rid,
                    "text": f"{rid} {requirement['text']} not asked · asked in {asked} of "
                    f"{len(others)} others",
                    "asked": asked,
                    "others": len(others),
                }
            )
    minutes, middle = row["minutes"], typical_values["minutes"]
    if _off(minutes, middle):
        flags.append(
            {"kind": "length", "text": f"{minutes} min · typical {middle:g} min", "value": minutes}
        )
    questions, middle = row["questions"], typical_values["questions"]
    if _off(questions, middle):
        flags.append(
            {
                "kind": "questions",
                "text": f"{questions} questions · typical {middle:g}",
                "value": questions,
            }
        )
    share, middle = row["candidate_share"], typical_values["candidate_share"]
    if share is not None and middle is not None and abs(share - middle) > SHARE_DIFFERENCE:
        flags.append(
            {
                "kind": "speaking_share",
                "text": f"Candidate spoke {share:g}% · typical {middle:g}%",
                "value": share,
            }
        )
    return flags


def job_consistency(rows: list[dict]) -> dict:
    """The job's consistency view from one row per checked interview: its
    session id, candidate, date, length in minutes, job-related questions,
    the candidate's share, the explored requirement ids, the requirements
    (id, text, priority) and its quality score and label."""
    count = len(rows)
    if count < MIN_INTERVIEWS:
        return {
            "count": count,
            "min_interviews": MIN_INTERVIEWS,
            "typical": None,
            "requirements": [],
            "interviews": [],
            "differ": 0,
        }
    typical_values = {
        "minutes": typical([row["minutes"] for row in rows]),
        "questions": typical([row["questions"] for row in rows]),
        "candidate_share": typical([row["candidate_share"] for row in rows]),
    }
    # The requirements of the latest-checked interview, in the job's order.
    requirements = rows[-1]["requirements"]
    summary = []
    for requirement in requirements:
        asked = sum(requirement["id"] in row["explored"] for row in rows)
        summary.append(
            {
                **requirement,
                "asked": asked,
                "total": count,
                "mostly_missed": asked * 2 < count,
            }
        )
    interviews = []
    for row in rows:
        flags = interview_flags(row, rows, typical_values, requirements)
        interviews.append(
            {
                **{key: value for key, value in row.items() if key != "requirements"},
                "flags": flags,
            }
        )
    interviews.sort(key=lambda item: (-len(item["flags"]), item["candidate_name"].lower()))
    return {
        "count": count,
        "min_interviews": MIN_INTERVIEWS,
        "typical": typical_values,
        "requirements": summary,
        "interviews": interviews,
        "differ": sum(bool(item["flags"]) for item in interviews),
    }
