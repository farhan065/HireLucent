"""Tools the Recruiter Agent can use.

A tool has two parts: a schema that tells the model what arguments to give,
and a handler that does the work. The model never gets database access: the
handler runs fixed code, and takes the user and the approved description
from the graph state, not from the model.
"""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from app.core.errors import ConflictError
from app.db.session import SessionLocal
from app.graphs.recruiter import interview_tools
from app.graphs.recruiter.drafts import latest_draft
from app.models.enums import JobStatus
from app.schemas.job import JobRequirements, ScoringWeights
from app.services import blogger, google_forms, job_service
from app.services.job_post import post_html

ALREADY_PUBLISHED_MESSAGE = "This job is already published."
FORM_IN_USE_MESSAGE = (
    "This form is already used by another job. Each job needs its own form, "
    "so its applications stay separate. Paste the link of a new form."
)
PUBLISHED_NO_CHANGES_MESSAGE = (
    "This job is already published, so its description can no longer change. "
    "Its requirements and weights can still be changed with Edit in the job "
    "brief."
)


class SaveJob(BaseModel):
    """Save the job with its requirements checklist and scoring weights. The
    approved job description is taken from the conversation. Call this only
    after the interviewer has approved the description. Calling it again
    before the job is published replaces the saved description, requirements
    and weights."""

    requirements: JobRequirements
    scoring_weights: ScoringWeights


def save_job(arguments: dict[str, Any], state: dict[str, Any]) -> tuple[str, dict]:
    """Validate the arguments and store the job. Returns a message for the
    model and the state fields to update.

    If the conversation already has a saved job that is not published yet,
    that job is updated with the newest description, requirements and
    weights, and keeps its job code.
    """
    data = SaveJob.model_validate(arguments)
    draft = latest_draft(state["messages"])
    if draft is None:
        raise ConflictError("There is no job description to save yet.")

    job_id = state.get("saved_job_id")
    with SessionLocal() as db:
        if job_id:
            if job_service.get_job(db, job_id).status != JobStatus.APPROVED:
                raise ConflictError(PUBLISHED_NO_CHANGES_MESSAGE)
            job = job_service.update_unpublished_job(
                db,
                job_id,
                title=draft.title,
                jd_text=draft.body,
                requirements=data.requirements,
                scoring_weights=data.scoring_weights,
            )
            # Starts like a first save, so the card shows as approved.
            return (
                f"Job saved again with job code {job.job_code}. The description, "
                "requirements and weights were replaced.",
                {},
            )
        job = job_service.create_job(
            db,
            title=draft.title,
            jd_text=draft.body,
            requirements=data.requirements,
            scoring_weights=data.scoring_weights,
            created_by=state["user_id"],
        )
    return f"Job saved with job code {job.job_code}.", {"saved_job_id": job.id}


class PublishJob(BaseModel):
    """Publish the saved job as a public post on the careers page. Call this
    only after the job is saved and the interviewer has given the link to
    the Google Form candidates will apply through."""

    form_link: str = Field(
        min_length=10,
        max_length=500,
        description="The form's address, exactly as the interviewer gave it.",
    )
    title: str | None = Field(
        default=None,
        min_length=3,
        max_length=255,
        description="Leave empty to use the job title.",
    )


def prepare_publication(arguments: dict[str, Any], state: dict[str, Any]) -> dict:
    """Check the form and collect everything the post will contain.

    This runs before the interviewer is asked, so what they approve is
    exactly what is published.
    """
    job_id = state.get("saved_job_id")
    if not job_id:
        raise ConflictError("Save the job before publishing it.")

    form = google_forms.get_form(arguments["form_link"])
    if not form.accepts_responses:
        raise ConflictError(
            "The form is not accepting responses. Publish it in Google Forms, "
            "then try again."
        )
    if not form.has_file_upload:
        raise ConflictError(
            "The form has no file upload question, so candidates cannot send "
            "a CV. Add one, then try again."
        )
    if not form.has_photo_upload:
        raise ConflictError(
            "The form needs a required photo upload question (its title must "
            "contain \"photo\"), used to confirm the candidate's identity at the "
            "interview. Add one, then try again."
        )
    if not form.has_consent_question:
        raise ConflictError(
            "The form needs a required consent question (its title must contain "
            "\"consent\") asking candidates to agree that their photo is used to "
            "confirm their identity. Add one, then try again."
        )

    with SessionLocal() as db:
        job = job_service.get_job(db, job_id)
        if job.status == JobStatus.PUBLISHED:
            raise ConflictError(ALREADY_PUBLISHED_MESSAGE)
        if job_service.form_is_used(db, form.form_id, except_job_id=job_id):
            raise ConflictError(FORM_IN_USE_MESSAGE)
        return {
            "form_link": arguments["form_link"],
            "title": arguments.get("title") or job.title,
            "job_code": job.job_code,
            "description": job.jd_text,
            "form_id": form.form_id,
            "form_url": form.public_url,
            "form_title": form.title,
        }


def publish_job(arguments: dict[str, Any], state: dict[str, Any]) -> tuple[str, dict]:
    """Publish the approved post and mark the job as published."""
    html = post_html(
        arguments["description"], arguments["job_code"], arguments["form_url"]
    )
    post_url = blogger.create_post(arguments["title"], html)
    with SessionLocal() as db:
        job_service.mark_published(
            db,
            state["saved_job_id"],
            form_id=arguments["form_id"],
            form_url=arguments["form_url"],
            post_url=post_url,
        )
    return f"Job published at {post_url}", {}


# What the model is shown.
TOOL_SCHEMAS: list[type[BaseModel]] = [
    SaveJob,
    PublishJob,
    interview_tools.GetCandidates,
    interview_tools.ScheduleInterviews,
    interview_tools.RescheduleInterview,
    interview_tools.CancelInterview,
]
TOOL_SCHEMAS_BY_NAME = {schema.__name__: schema for schema in TOOL_SCHEMAS}

# What runs when the model asks for a tool.
ToolHandler = Callable[[dict[str, Any], dict[str, Any]], tuple[str, dict]]
TOOL_HANDLERS: dict[str, ToolHandler] = {
    "SaveJob": save_job,
    "PublishJob": publish_job,
    "GetCandidates": interview_tools.get_candidates,
    "ScheduleInterviews": interview_tools.schedule_interviews,
    "RescheduleInterview": interview_tools.reschedule_interview,
    "CancelInterview": interview_tools.cancel_interview,
}

# Tools that change something or act outside the app. They always wait for
# the interviewer's approval before running.
EXTERNAL_ACTIONS = {
    "SaveJob",
    "PublishJob",
    "ScheduleInterviews",
    "RescheduleInterview",
    "CancelInterview",
}

# The question bank search on the RAG MCP server. It is the only tool the
# agent has during an interview, when it may read but never act.
QUESTION_BANK_TOOL = "search_question_bank"
INTERVIEW_TOOLS = {QUESTION_BANK_TOOL}

# Work done before the interviewer is asked: the checked arguments go in and
# the full details to approve come out. Because these details are built by
# the app, they are used as approved and cannot be replaced from the browser.
Preparer = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
PREPARERS: dict[str, Preparer] = {
    "PublishJob": prepare_publication,
    "ScheduleInterviews": interview_tools.prepare_schedule,
    "RescheduleInterview": interview_tools.prepare_reschedule,
    "CancelInterview": interview_tools.prepare_cancel,
}
