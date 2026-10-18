"""The component scores and the suitability label. Rule-based, no AI call.

    interview score = average score of the evaluated answers
    overall score   = 0.4 x CV score + 0.6 x interview score

The CV score is the candidate's final score from CV screening. Small talk is
not evaluated, so it never counts. The label is decision support only: the
hiring decision stays with the interviewer.
"""

# The split confirmed for the overall score.
CV_SHARE = 0.4
INTERVIEW_SHARE = 0.6

# Where each suitability label starts.
STRONG_FIT_SCORE = 70
POSSIBLE_FIT_SCORE = 60

STRONG_FIT = "strong_fit"
POSSIBLE_FIT = "possible_fit"
NOT_A_FIT = "not_a_fit"


def evaluated(pairs: list[dict]) -> list[dict]:
    """The pairs that were evaluated, so not small talk."""
    return [pair for pair in pairs if pair.get("evaluation")]


def interview_score(pairs: list[dict]) -> float | None:
    """The average score of the evaluated answers, or None when the interview
    had no job-related questions."""
    scores = [pair["evaluation"]["score"] for pair in evaluated(pairs)]
    return round(sum(scores) / len(scores), 1) if scores else None


def overall_score(cv: float | None, interview: float | None) -> float | None:
    """Both parts are needed. Without one of them there is no overall score,
    rather than a number that hides what is missing."""
    if cv is None or interview is None:
        return None
    return round(CV_SHARE * cv + INTERVIEW_SHARE * interview, 1)


def suitability(overall: float | None) -> str | None:
    """strong_fit from 70, possible_fit from 60, not_a_fit below."""
    if overall is None:
        return None
    if overall >= STRONG_FIT_SCORE:
        return STRONG_FIT
    if overall >= POSSIBLE_FIT_SCORE:
        return POSSIBLE_FIT
    return NOT_A_FIT
