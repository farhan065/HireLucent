"""Schemas for job profiles: requirements, scoring weights and API responses."""

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Category = Literal["technical_skills", "experience", "qualifications"]
Priority = Literal["must_have", "preferred"]

# Scoring must use job-related criteria only (BID N20), so a requirement that
# mentions a protected characteristic is rejected.
PROTECTED_TERMS = (
    "age",
    "gender",
    "male",
    "female",
    "nationality",
    "religion",
    "ethnicity",
    "marital status",
    "married",
    "unmarried",
)
_PROTECTED_PATTERN = re.compile(
    r"\b(" + "|".join(PROTECTED_TERMS) + r")\b", re.IGNORECASE
)


class RequirementItem(BaseModel):
    """One requirement of a job, for example "Python web development"."""

    id: str = Field(pattern=r"^R\d+$", description="Short label such as R1.")
    text: str = Field(min_length=3, max_length=200)
    category: Category
    priority: Priority
    keywords: list[str] = Field(
        default_factory=list,
        description="Accepted terms, used by the must-have check and ATS score.",
    )

    @field_validator("text")
    @classmethod
    def no_protected_characteristics(cls, text: str) -> str:
        if _PROTECTED_PATTERN.search(text):
            raise ValueError(
                "Requirements must be job-related and cannot refer to age, gender, "
                "nationality, religion, ethnicity or marital status."
            )
        return text.strip()

    @field_validator("keywords")
    @classmethod
    def clean_keywords(cls, keywords: list[str]) -> list[str]:
        """Lower-case, trim and remove empty or repeated keywords."""
        cleaned = [keyword.strip().lower() for keyword in keywords]
        return list(dict.fromkeys(keyword for keyword in cleaned if keyword))


class JobRequirements(BaseModel):
    """The requirements checklist the interviewer confirms for a job."""

    # Required, so the assistant must state it. Use 0 when there is no minimum.
    min_experience_years: int = Field(ge=0, le=50)
    items: list[RequirementItem] = Field(min_length=1)

    @model_validator(mode="after")
    def ids_are_unique(self) -> "JobRequirements":
        ids = [item.id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Each requirement must have a different id.")
        return self


class ScoringWeights(BaseModel):
    """How much each dimension counts towards the criteria score."""

    technical_skills: float = Field(ge=0, le=1)
    experience: float = Field(ge=0, le=1)
    qualifications: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def weights_add_up_to_one(self) -> "ScoringWeights":
        total = self.technical_skills + self.experience + self.qualifications
        if abs(total - 1.0) > 0.01:
            raise ValueError("The three weights must add up to 1.0.")
        return self


class JobProfileUpdate(BaseModel):
    """Body for changing a job's requirements and weights."""

    requirements: JobRequirements
    scoring_weights: ScoringWeights


class JobSummary(BaseModel):
    """A job as shown in the dashboard list."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_code: str
    title: str
    status: str
    form_url: str | None
    post_url: str | None
    published_at: datetime | None
    created_at: datetime
    candidate_counts: dict[str, int] = Field(
        default_factory=dict, description="Number of candidates in each status."
    )


class JobDetail(JobSummary):
    """A job with its full description, requirements and weights."""

    jd_text: str
    requirements: JobRequirements
    scoring_weights: ScoringWeights
    is_locked: bool = Field(
        default=False,
        description="True once a CV has been screened; the profile cannot change.",
    )
