"""Database reads and writes for the Candidate Feedback graph.

Kept apart from the graph so its nodes stay easy to follow and to test. The
evidence handed to the graph holds only job-related facts: requirement
results and the CV's profile and skills from screening, or the approved
report's points. Scores, ranks,
other candidates, transcript quotes, the identity check and the
interviewer's private note are never loaded.
"""

import re
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.session import SessionLocal
from app.graphs.feedback import templates
from app.graphs.qa_analysis.segmentation import mask_text
from app.models import Assessment, Candidate, CandidateFeedback, Job
from app.models.enums import (
    AssessmentStatus,
    CandidateStatus,
    Decision,
    FeedbackKind,
    FeedbackStatus,
)

# Every point is passed on (no limit on how many); each is cut to a short
# length so one long requirement cannot crowd out the rest.
MAX_POINT_CHARS = 300
# Candidates rejected at screening: not shortlisted and never interviewed.
SCREENING_REJECTED = (
    CandidateStatus.SCREENED,
    CandidateStatus.EXCLUDED,
    CandidateStatus.SCREENING_FAILED,
)
_MISSING = re.compile(r"^Missing must-have \((?P<id>[^)]+)\): (?P<text>.+)$")
_EXPERIENCE = re.compile(r"at least (?P<years>\d+) years")

# Why the candidate was not chosen, which decides how the email words it.
MUST_HAVE = "must_have"
PREFERRED = "preferred"
NONE = "none"
# The id of the candidate's CV profile among the strengths.
PROFILE_ID = "CV"
# Capitalised words that are never part of a name, for _without_name.
NOT_NAMES = (
    "The|A|An|And|As|At|By|For|From|In|On|Of|With|Who|Is|Has|Was|Brings|Leads|Works"
    "|Senior|Junior|Lead|Principal|Staff|Frontend|Backend|Full|Software|Engineer|Developer"
)


def _point(ref: str, text: str, note: str) -> dict:
    return {"id": ref, "text": mask_text(text.strip())[:MAX_POINT_CHARS], "note": note}


def feedback_kind(candidate: Candidate, approved: bool) -> str | None:
    """Which email the candidate can get now, or None."""
    if candidate.status == CandidateStatus.SCREENING_FAILED:
        return FeedbackKind.CV_UNREADABLE
    if candidate.decision == Decision.HIRE and approved:
        return FeedbackKind.HIRE
    if candidate.decision == Decision.REJECT and approved:
        return FeedbackKind.INTERVIEW_REJECT
    if candidate.status in SCREENING_REJECTED:
        return FeedbackKind.SCREENING_REJECT
    return None


def _has_approved_report(db, candidate_id: int) -> Assessment | None:
    return db.scalar(
        select(Assessment)
        .where(
            Assessment.candidate_id == candidate_id,
            Assessment.status == AssessmentStatus.APPROVED,
        )
        .order_by(Assessment.approved_at.desc())
        .limit(1)
    )


def _without_name(text: str, full_name: str) -> str:
    """The text with the candidate's name taken out, so the AI never sees it:
    the whole name first, then each part of it. A single part is only taken
    out when written as a name (capitalised), so a name like "Joy" leaves
    the word "joy" alone."""
    parts = [part.strip(".,") for part in (full_name or "").split()]
    parts = [
        part for part in parts if len(part) > 1 and part.lower() not in templates.NAME_PREFIXES
    ]
    if not parts:
        return text
    whole = r"\s+".join(re.escape(part) for part in parts)
    text = re.sub(rf"\b{whole}\b('s)?", r"the candidate\1", text, flags=re.IGNORECASE)
    for part in parts:
        written = {part.capitalize(), part.upper(), part}
        pattern = "|".join(re.escape(form) for form in written)
        text = re.sub(rf"\b(?:{pattern})\b('s)?", r"the candidate\1", text)
    # The CV may spell the name differently from the form ("Tahsin" and
    # "Tashsin"): name-like words right beside a name found go too.
    word = rf"(?!(?:{NOT_NAMES})\b)[A-Z][a-z]+"
    text = re.sub(rf"\b(?:{word}\s+){{1,2}}(?=the candidate\b)", "", text)
    text = re.sub(rf"\bthe candidate(?:\s+{word}){{1,2}}\b", "the candidate", text)
    return re.sub(r"(?:the candidate\s+){2,}", "the candidate ", text)


def _profile(candidate: Candidate) -> list[dict]:
    """The candidate's profile from the CV, so the email can lead with their
    main area even when it is not this role's focus: the CV summary, or the
    job titles they held when the CV has no summary. Contact details and
    the candidate's name are taken out."""
    parsed = candidate.cv_parsed or {}
    summary = _without_name(str(parsed.get("summary") or "").strip(), candidate.full_name)
    if summary:
        return [_point(PROFILE_ID, summary, "profile in the CV")]
    titles = []
    for job in parsed.get("experience") or []:
        title = str((job or {}).get("title") or "").strip()
        if title and title.lower() not in {seen.lower() for seen in titles}:
            titles.append(title)
    if titles:
        return [_point(PROFILE_ID, f"Roles in the CV: {', '.join(titles)}", "roles in the CV")]
    return []


def _screening_points(candidate: Candidate, job: Job) -> tuple[list, list, str]:
    """Strengths and growth areas from the CV screening, and the reason."""
    result = candidate.screening_result
    if candidate.status == CandidateStatus.EXCLUDED and result and result.excluded_reason:
        growth = []
        for line in result.excluded_reason.splitlines():
            missing = _MISSING.match(line.strip())
            years = _EXPERIENCE.search(line)
            if missing:
                growth.append(
                    _point(missing["id"], missing["text"], "must-have · not found in the CV")
                )
            elif years:
                growth.append(
                    _point(
                        "EXP",
                        f"At least {years['years']} years of professional experience",
                        "minimum experience · not met",
                    )
                )
            elif line.strip():
                # A reason in another wording is still a must-have not met.
                growth.append(_point(f"MH{len(growth) + 1}", line, "must-have · not met"))
        skills = (candidate.cv_parsed or {}).get("skills") or []
        strengths = _profile(candidate) + [
            _point(f"SK{number}", str(skill), "skill in the CV")
            for number, skill in enumerate(skills, start=1)
            if str(skill).strip()
        ]
        return strengths, growth, MUST_HAVE if growth else NONE

    matches = (result.requirement_matches if result else None) or []
    strengths = _profile(candidate) + [
        _point(item["id"], item["text"], f"{item['priority'].replace('_', '-')} · met")
        for item in matches
        if item["status"] == "met"
    ]
    growth = [
        _point(
            item["id"],
            item["text"],
            f"preferred · {'partly met' if item['status'] == 'partially_met' else 'not met'}",
        )
        for item in matches
        if item["priority"] == "preferred" and item["status"] in ("unmet", "partially_met")
    ]
    # Unmet ones first: they matter more than partly met ones.
    growth.sort(key=lambda point: "partly" in point["note"])
    return strengths, growth, PREFERRED if growth else NONE


def _report_points(assessment: Assessment) -> tuple[list, list, str]:
    """Strengths and growth areas from the approved interview report."""
    strengths = [
        _point(claim["id"], claim["text"], "report strength")
        for claim in assessment.strengths or []
    ]
    growth = [
        _point(claim["id"], claim["text"], "report weakness")
        for claim in assessment.weaknesses or []
    ]
    return strengths, growth, MUST_HAVE if growth else NONE


def requirement_lines(requirements: dict) -> str:
    """The job's requirements as lines, with their keywords."""
    lines = []
    for item in requirements.get("items", []):
        keywords = ", ".join(item.get("keywords") or [])
        lines.append(f"- {item['id']}: {item['text']}" + (f" ({keywords})" if keywords else ""))
    return "\n".join(lines)


def load_evidence(candidate_id: int) -> dict | None:
    """Everything the email may be written from, or None when the candidate
    cannot get an email now (for example, shortlisted and not decided)."""
    with SessionLocal() as db:
        candidate = db.get(Candidate, candidate_id)
        if candidate is None:
            return None
        job = db.get(Job, candidate.job_id)
        assessment = _has_approved_report(db, candidate_id)
        kind = feedback_kind(candidate, assessment is not None)
        if kind is None:
            return None
        requirements = job.requirements or {}
        evidence = {
            "kind": kind,
            "job_id": job.id,
            "job_title": job.title,
            "first_name": templates.first_name(candidate.full_name),
            "level": templates.role_level(job.title, requirements.get("min_experience_years")),
            "strengths": [],
            "growth": [],
            "reason": NONE,
            # The job's own requirements: what the role needs may be named.
            "requirements": requirement_lines(requirements),
        }
        if kind == FeedbackKind.SCREENING_REJECT:
            strengths, growth, reason = _screening_points(candidate, job)
        elif kind == FeedbackKind.INTERVIEW_REJECT:
            strengths, growth, reason = _report_points(assessment)
        else:
            return evidence
        return {**evidence, "strengths": strengths, "growth": growth, "reason": reason}


def recipient(candidate_id: int) -> str | None:
    """The candidate's email address, read only when the email is sent, so
    it is never kept in the graph's saved state."""
    with SessionLocal() as db:
        candidate = db.get(Candidate, candidate_id)
        return candidate.email if candidate else None


def save_draft(candidate_id: int, values: dict) -> None:
    """Keep the draft waiting for the interviewer's review."""
    with SessionLocal() as db:
        feedback = db.scalar(
            select(CandidateFeedback).where(CandidateFeedback.candidate_id == candidate_id)
        )
        if feedback is None:
            feedback = CandidateFeedback(candidate_id=candidate_id, job_id=values["job_id"])
            db.add(feedback)
        feedback.kind = values["kind"]
        feedback.written_by = values["written_by"]
        feedback.subject = values["subject"]
        feedback.body = values["body"]
        feedback.evidence = values.get("evidence_used", [])
        feedback.warnings = values.get("warnings", [])
        feedback.attempts = values.get("attempts", 0)
        feedback.status = FeedbackStatus.WAITING_REVIEW
        feedback.error_message = None
        feedback.sent_anyway = False
        feedback.approved_by = None
        feedback.approved_at = None
        db.commit()


def _feedback(db, candidate_id: int) -> CandidateFeedback | None:
    return db.scalar(
        select(CandidateFeedback).where(CandidateFeedback.candidate_id == candidate_id)
    )


def mark_sending(candidate_id: int, reviewer_id: int) -> None:
    with SessionLocal() as db:
        feedback = _feedback(db, candidate_id)
        feedback.status = FeedbackStatus.SENDING
        feedback.approved_by = reviewer_id
        feedback.approved_at = datetime.now(timezone.utc)
        db.commit()


def mark_failed(candidate_id: int, message: str) -> None:
    """The email could not be sent. The draft is kept for Try again."""
    with SessionLocal() as db:
        feedback = _feedback(db, candidate_id)
        feedback.status = FeedbackStatus.FAILED
        feedback.error_message = message[:255]
        db.commit()


def record_sent(candidate_id: int, reviewer_id: int, sent_anyway: bool) -> None:
    """The email is sent: keep when, who approved it, and lock the decision.
    A candidate rejected at screening gets the "reject" decision now."""
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        feedback = _feedback(db, candidate_id)
        feedback.status = FeedbackStatus.SENT
        feedback.sent_at = now
        feedback.error_message = None
        feedback.sent_anyway = sent_anyway
        candidate = db.get(Candidate, candidate_id)
        if candidate.decision is None:
            candidate.decision = (
                Decision.HIRE if feedback.kind == FeedbackKind.HIRE else Decision.REJECT
            )
            candidate.decided_by = reviewer_id
            candidate.decided_at = now
        db.commit()


def discard(candidate_id: int) -> None:
    with SessionLocal() as db:
        feedback = _feedback(db, candidate_id)
        if feedback is not None:
            feedback.status = FeedbackStatus.DISCARDED
            feedback.warnings = []
            db.commit()
