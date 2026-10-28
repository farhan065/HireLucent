"""Database reads and writes for the CV Screening graph.

Kept apart from the graph so its nodes stay easy to follow and to test.
"""

from sqlalchemy import and_, func, or_, select

from sqlalchemy.orm import selectinload

from app.db.session import SessionLocal
from app.graphs.screening import matching, scoring
from app.models import Candidate, Job, ScreeningResult
from app.models.enums import CandidateStatus

# Candidates that may still need screening: new ones, and ones that failed.
TO_SCREEN = (CandidateStatus.APPLIED, CandidateStatus.SCREENING_FAILED)


def _waiting(job_id: int):
    """Candidates of a job with screening steps still to run: no result yet,
    or they met the must-haves but have not been scored."""
    return (
        select(Candidate)
        .outerjoin(ScreeningResult)
        .where(
            Candidate.job_id == job_id,
            Candidate.status.in_(TO_SCREEN),
            or_(
                ScreeningResult.id.is_(None),
                and_(
                    ScreeningResult.excluded_reason.is_(None),
                    ScreeningResult.final_score.is_(None),
                ),
            ),
        )
    )


def load_cvs(job_id: int) -> list[dict]:
    """The CVs of a job that are waiting to be screened. A CV that was read
    and parsed before carries its text and facts, so it is not read again,
    and one that met the must-haves before is not checked again."""
    with SessionLocal() as db:
        cvs = []
        query = _waiting(job_id).options(selectinload(Candidate.screening_result))
        for candidate in db.scalars(query.order_by(Candidate.id)):
            cv = {"candidate_id": candidate.id, "cv_path": candidate.cv_path}
            if candidate.cv_parsed:
                cv |= {
                    "text": candidate.cv_text,
                    "text_source": candidate.cv_text_source,
                    "parsed": candidate.cv_parsed,
                    "must_haves_met": candidate.screening_result is not None,
                }
                if candidate.screening_result and candidate.screening_result.requirement_matches:
                    cv["matches"] = candidate.screening_result.requirement_matches
            cvs.append(cv)
        return cvs


def count_to_screen(job_id: int) -> int:
    """How many CVs of a job are waiting to be screened."""
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(_waiting(job_id).subquery()))


def load_job(job_id: int) -> dict:
    """What every CV of the job is checked and scored against."""
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        return {
            "title": job.title,
            "jd_text": job.jd_text,
            "requirements": job.requirements,
            "scoring_weights": job.scoring_weights,
        }


def save_cv(candidate_id: int, text: str, source: str, parsed: dict) -> None:
    """Keep the text and the structured facts read from a CV."""
    with SessionLocal() as db:
        candidate = db.get(Candidate, candidate_id)
        candidate.cv_text = text
        candidate.cv_text_source = source
        candidate.cv_parsed = parsed
        candidate.screening_error = None
        candidate.status = CandidateStatus.APPLIED
        db.commit()


def save_failure(candidate_id: int, reason: str) -> None:
    """Mark a CV that could not be processed, with the reason."""
    with SessionLocal() as db:
        candidate = db.get(Candidate, candidate_id)
        candidate.status = CandidateStatus.SCREENING_FAILED
        candidate.screening_error = reason[:255]
        db.commit()


def save_exclusion(candidate_id: int, reasons: list[str]) -> None:
    """Exclude a candidate who misses a must-have, with every reason."""
    with SessionLocal() as db:
        candidate = db.get(Candidate, candidate_id)
        candidate.status = CandidateStatus.EXCLUDED
        candidate.screening_error = None
        _result(db, candidate_id).excluded_reason = "\n".join(reasons)
        db.commit()


def save_passed(candidate_id: int) -> None:
    """Record that a candidate met the must-haves. Matching and scoring
    fill in the rest of the result in later steps."""
    with SessionLocal() as db:
        candidate = db.get(Candidate, candidate_id)
        candidate.screening_error = None
        candidate.status = CandidateStatus.APPLIED
        _result(db, candidate_id).excluded_reason = None
        db.commit()


def save_matches(candidate_id: int, matches: list[dict], score: float) -> None:
    """Keep the result of matching each requirement against the CV."""
    with SessionLocal() as db:
        candidate = db.get(Candidate, candidate_id)
        candidate.screening_error = None
        candidate.status = CandidateStatus.APPLIED
        result = _result(db, candidate_id)
        result.requirement_matches = matches
        result.match_score = score
        db.commit()


def save_result(candidate_id: int, scores: dict) -> None:
    """Keep the scores and mark the candidate as screened. Their screening
    is complete, so the next run skips them."""
    with SessionLocal() as db:
        candidate = db.get(Candidate, candidate_id)
        candidate.screening_error = None
        candidate.status = CandidateStatus.SCREENED
        result = _result(db, candidate_id)
        result.dimension_scores = scores["dimensions"]
        result.ats_score = scores["ats"]["score"]
        result.ats_details = scores["ats"]
        result.criteria_score = scores["criteria_score"]
        result.final_score = scores["final_score"]
        result.justification = scores["summary"]
        db.commit()


def rerank(job_id: int) -> None:
    """Rank the job's candidates again, after a screening or a deletion:
    matched candidates by match score, scored candidates by final score.
    Anyone else has no rank."""
    with SessionLocal() as db:
        rows = db.execute(
            select(Candidate.id, Candidate.full_name, ScreeningResult)
            .join(ScreeningResult)
            .where(
                Candidate.job_id == job_id,
                Candidate.status != CandidateStatus.EXCLUDED,
                ScreeningResult.requirement_matches.is_not(None),
            )
        ).all()
        candidates = [
            {
                "candidate_id": candidate_id,
                "full_name": full_name,
                "match_score": result.match_score or 0.0,
                "matches": result.requirement_matches,
                "final_score": result.final_score,
                "criteria_score": result.criteria_score,
            }
            for candidate_id, full_name, result in rows
        ]
        scored = [c for c in candidates if c["final_score"] is not None]
        match_ranks = _positions(matching.rank_order(candidates))
        final_ranks = _positions(scoring.final_order(scored))
        for result in db.scalars(
            select(ScreeningResult).join(Candidate).where(Candidate.job_id == job_id)
        ):
            result.rank = match_ranks.get(result.candidate_id)
            result.final_rank = final_ranks.get(result.candidate_id)
        db.commit()


def _positions(ordered_ids: list[int]) -> dict[int, int]:
    return {candidate_id: rank for rank, candidate_id in enumerate(ordered_ids, 1)}


def _result(db, candidate_id: int) -> ScreeningResult:
    result = db.scalar(
        select(ScreeningResult).where(ScreeningResult.candidate_id == candidate_id)
    )
    if result is None:
        result = ScreeningResult(candidate_id=candidate_id)
        db.add(result)
    return result
