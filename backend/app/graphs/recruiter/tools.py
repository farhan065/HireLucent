"""Tools the Recruiter Agent can use.

A tool has two parts: a schema that tells the model what arguments to give,
and a handler that does the work. The model never gets database access: the
handler runs fixed code and takes the user from the graph state, not from
the model.
"""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from app.db.session import SessionLocal
from app.schemas.job import JobRequirements, ScoringWeights
from app.services import job_service


class SaveJob(BaseModel):
    """Save the approved job description with its requirements checklist and
    scoring weights. Call this only after the interviewer has approved."""

    title: str = Field(min_length=3, max_length=255, description="The job title.")
    jd_text: str = Field(min_length=50, description="The full approved description.")
    requirements: JobRequirements
    scoring_weights: ScoringWeights


def save_job(arguments: dict[str, Any], state: dict[str, Any]) -> tuple[str, dict]:
    """Validate the arguments and store the job. Returns a message for the
    model and the state fields to update."""
    data = SaveJob.model_validate(arguments)
    with SessionLocal() as db:
        job = job_service.create_job(
            db,
            title=data.title,
            jd_text=data.jd_text,
            requirements=data.requirements,
            scoring_weights=data.scoring_weights,
            created_by=state["user_id"],
        )
    return f"Job saved with job code {job.job_code}.", {"saved_job_id": job.id}


# What the model is shown.
TOOL_SCHEMAS: list[type[BaseModel]] = [SaveJob]

# What runs when the model asks for a tool.
ToolHandler = Callable[[dict[str, Any], dict[str, Any]], tuple[str, dict]]
TOOL_HANDLERS: dict[str, ToolHandler] = {"SaveJob": save_job}

# Tools that change something or act outside the app. They always wait for
# the interviewer's approval before running.
EXTERNAL_ACTIONS = {"SaveJob"}