"""Schemas for the structured facts read from a CV.

Only job-related facts are kept. Protected characteristics such as age,
gender, nationality, religion or marital status are never extracted
(BID N20).
"""

from pydantic import BaseModel, Field


class Education(BaseModel):
    degree: str = Field("", description='For example "BSc".')
    field: str = Field("", description='For example "Computer Science".')
    institution: str = ""
    year: str = Field("", description="Graduation year, or the years attended.")


class WorkExperience(BaseModel):
    title: str = Field("", description="Job title.")
    company: str = ""
    start: str = Field("", description='As written in the CV, for example "Jan 2021".')
    end: str = Field("", description='As written in the CV, or "Present".')
    description: str = Field("", description="What the person did, in brief.")


class Project(BaseModel):
    name: str = ""
    description: str = ""
    technologies: list[str] = Field(default_factory=list)


class CVContent(BaseModel):
    """The part of a CV the AI reads."""

    summary: str = Field("", description="Two sentences on the professional profile.")
    skills: list[str] = Field(description="Technical and professional skills.")
    education: list[Education]
    experience: list[WorkExperience]
    total_experience_years: float = Field(
        ge=0,
        le=60,
        description=(
            "Years of professional work, added up from the dates of the work "
            "experience. 0 when the CV gives no dates."
        ),
    )
    certifications: list[str]
    projects: list[Project]


class ContactDetails(BaseModel):
    """Found by pattern matching in the application, never sent to the AI."""

    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)


class ParsedCV(CVContent):
    """Everything kept from a CV, stored with the candidate."""

    contact: ContactDetails
