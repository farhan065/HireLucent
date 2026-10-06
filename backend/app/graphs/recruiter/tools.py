"""Tools the Recruiter Agent can use.

A tool has two parts: a schema that tells the model what arguments to give,
and a handler that does the work. The model never gets database access: the
handler runs fixed code, and takes the user and the approved description
from the graph state, not from the model.
"""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from app.core.errors import ConflictError
from app.db.session import SessionLocal
from app.graphs.recruiter.drafts import latest_draft
from app.schemas.job import JobRequirements, ScoringWeights
from app.services import job_service

ALREADY_SAVED_MESSAGE = (
    "This conversation already has a saved job. Start a new job conversation "
    "for another role."
)


class SaveJob(BaseModel):
    """Save the job with its requirements checklist and scoring weights. The
    approved job description is taken from the conversation. Call this only
    after the interviewer has approved the description."""

    requirements: JobRequirements
    scoring_weights: ScoringWeights


def save_job(arguments: dict[str, Any], state: dict[str, Any]) -> tuple[str, dict]:
    """Validate the arguments and store the job. Returns a message for the
    model and the state fields to update."""
    if state.get("saved_job_id"):
        raise ConflictError(ALREADY_SAVED_MESSAGE)
    data = SaveJob.model_validate(arguments)
    draft = latest_draft(state["messages"])
    if draft is None:
        raise ConflictError("There is no job description to save yet.")

    with SessionLocal() as db:
        job = job_service.create_job(
            db,
            title=draft.title,
            jd_text=draft.body,
            requirements=data.requirements,
            scoring_weights=data.scoring_weights,
            created_by=state["user_id"],
        )
    return f"Job saved with job code {job.job_code}.", {"saved_job_id": job.id}


# What the model is shown.
TOOL_SCHEMAS: list[type[BaseModel]] = [SaveJob]
TOOL_SCHEMAS_BY_NAME = {schema.__name__: schema for schema in TOOL_SCHEMAS}

# What runs when the model asks for a tool.
ToolHandler = Callable[[dict[str, Any], dict[str, Any]], tuple[str, dict]]
TOOL_HANDLERS: dict[str, ToolHandler] = {"SaveJob": save_job}

# Tools that change something or act outside the app. They always wait for
# the interviewer's approval before running.
EXTERNAL_ACTIONS = {"SaveJob"}
