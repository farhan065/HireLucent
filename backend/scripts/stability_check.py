"""Check that screening scores are stable: score one already screened
candidate again a few times and compare the results with the saved ones.

Usage (inside the backend container):
    python -m scripts.stability_check --candidate 12 --runs 3

Nothing is saved: the candidate's scores, rank and status stay as they are.
Each run makes two AI calls (requirement matching and scoring), so keep the
number of runs small. Only IDs and numbers are printed, never names or CV
text.
"""

import argparse
import sys

from sqlalchemy.orm import selectinload

from app.db.session import SessionLocal
from app.graphs.screening import matching, scoring, store
from app.models import Candidate

COLUMNS = ("match", "technical_skills", "experience", "qualifications", "criteria", "ats", "final")
HEADINGS = ("Match", "Tech", "Exp", "Qual", "Criteria", "ATS", "Final")


def load(candidate_id: int) -> tuple[dict, dict, dict]:
    """The candidate's CV, their saved scores and their job's rules."""
    with SessionLocal() as db:
        candidate = db.get(
            Candidate, candidate_id, options=[selectinload(Candidate.screening_result)]
        )
        if candidate is None:
            sys.exit(f"Candidate {candidate_id} does not exist.")
        scores = candidate.scores
        if not scores or not candidate.cv_parsed:
            sys.exit(f"Candidate {candidate_id} has no final score yet. Pick a scored candidate.")
        cv = {"text": candidate.cv_text, "parsed": candidate.cv_parsed}
        saved = {
            "match": candidate.match_score,
            **{name: scores["dimensions"][name]["score"] for name in scoring.DIMENSIONS},
            "criteria": scores["criteria_score"],
            "ats": scores["ats_score"],
            "final": scores["final_score"],
            "statuses": [item["status"] for item in candidate.requirement_matches or []],
        }
        job_id = candidate.job_id
    return cv, saved, store.load_job(job_id) | {"job_id": job_id}


def score_once(candidate_id: int, cv: dict, job: dict) -> dict:
    """Match and score the CV the same way screening does, without saving.
    The CV's sections are stored again in the vector store, unchanged."""
    matches = matching.match(candidate_id, job["job_id"], job["requirements"], cv)
    ats = scoring.ats_score(job["requirements"], job["jd_text"], cv["text"])
    answer = scoring.dimension_scores(job["title"], job["requirements"], matches, cv["parsed"])
    totals = scoring.combine(answer["dimensions"], job["scoring_weights"], ats["score"])
    return {
        "match": matching.match_score(matches),
        **{name: answer["dimensions"][name]["score"] for name in scoring.DIMENSIONS},
        "criteria": totals["criteria_score"],
        "ats": ats["score"],
        "final": totals["final_score"],
        "statuses": [item["status"] for item in matches],
    }


def row(label: str, values: dict) -> str:
    cells = "".join(
        f"{values[key]:>10g}" if values[key] is not None else f"{'-':>10}" for key in COLUMNS
    )
    return f"{label:<12}{cells}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--candidate", type=int, required=True, help="ID of a scored candidate")
    parser.add_argument("--runs", type=int, default=3, choices=range(1, 6), metavar="1-5")
    args = parser.parse_args()

    cv, saved, job = load(args.candidate)
    print(f"Candidate {args.candidate}, job {job['job_id']}: {args.runs} new runs\n")
    print(f"{'':<12}" + "".join(f"{heading:>10}" for heading in HEADINGS))
    print(row("Saved", saved))

    results = [saved]
    for run in range(1, args.runs + 1):
        result = score_once(args.candidate, cv, job)
        results.append(result)
        print(row(f"Run {run}", result))

    spread = {
        key: round(max(r[key] for r in results) - min(r[key] for r in results), 1)
        for key in COLUMNS
    }
    print(row("Difference", spread))

    # A requirement counts as changed when the runs disagree on its result.
    changed = sum(
        1
        for position in range(len(saved["statuses"]))
        if len({r["statuses"][position] for r in results if len(r["statuses"]) > position}) > 1
    )
    print(
        f"\nLargest final score difference: {spread['final']:g} points."
        f"\nRequirements whose met / partly / not met result changed: "
        f"{changed} of {len(saved['statuses'])}."
    )


if __name__ == "__main__":
    main()
