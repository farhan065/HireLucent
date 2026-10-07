"""Building blocks shared by the Recruiter Agent and chat tests."""

from langchain_core.language_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.graphs.recruiter import graph as recruiter
from app.services.google_forms import FormLinkError

DRAFT_ONE = (
    "# Backend Engineer\n\n## About the Role\n"
    "You will build and maintain REST APIs in Python for our platform."
)
DRAFT_TWO = (
    "# Senior Backend Engineer\n\n## About the Role\n"
    "You will lead the design of REST APIs in Python for our platform."
)
VALID_ARGS = {
    "requirements": {
        "min_experience_years": 2,
        "items": [
            {
                "id": "R1",
                "text": "Python web development",
                "category": "technical_skills",
                "priority": "must_have",
                "keywords": ["python", "django"],
            }
        ],
    },
    "scoring_weights": {
        "technical_skills": 0.5,
        "experience": 0.3,
        "qualifications": 0.2,
    },
}
BAD_ARGS = {
    **VALID_ARGS,
    "scoring_weights": {"technical_skills": 0.9, "experience": 0.9, "qualifications": 0.9},
}


def save_call(args: dict, call_id: str = "call-1") -> AIMessage:
    """A model reply that asks to save the job."""
    return AIMessage(
        content="", tool_calls=[{"name": "SaveJob", "args": args, "id": call_id}]
    )


def fake_save_job(saved: list[dict]):
    """A stand-in for the real save tool that records what it was given."""

    def handler(arguments: dict, state: dict) -> tuple[str, dict]:
        recruiter.TOOL_SCHEMAS[0].model_validate(arguments)
        saved.append({"arguments": arguments, "user_id": state["user_id"]})
        return "Job saved with job code HL-BE-01.", {"saved_job_id": 7}

    return handler


FORM_LINK = "https://docs.google.com/forms/d/1AbCdEfGhIjKlMnOpQrStUvWxYz/edit"
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQL/viewform"
POST_URL = "https://careers.example.com/2026/10/backend-engineer.html"


def publish_call(form_link: str = FORM_LINK, call_id: str = "publish-1") -> AIMessage:
    """A model reply that asks to publish the job."""
    return AIMessage(
        content="",
        tool_calls=[{"name": "PublishJob", "args": {"form_link": form_link}, "id": call_id}],
    )


def fake_prepare_publication(arguments: dict, state: dict) -> dict:
    """A stand-in for the real check, which reads the form from Google."""
    if "docs.google.com/forms/d/" not in arguments["form_link"]:
        raise FormLinkError("That is not a Google Form link.")
    return {
        "form_link": arguments["form_link"],
        "title": arguments.get("title") or "Backend Engineer",
        "job_code": "HL-BE-01",
        "description": "## About the Role\nYou will build REST APIs.",
        "form_id": "1AbCdEfGhIjKlMnOpQrStUvWxYz",
        "form_url": FORM_URL,
        "form_title": "Backend Engineer application",
    }


def fake_publish_job(published: list[dict]):
    """A stand-in for the real publishing tool that records what it was given."""

    def handler(arguments: dict, state: dict) -> tuple[str, dict]:
        published.append(arguments)
        return f"Job published at {POST_URL}", {}

    return handler


def graph_with_replies(
    monkeypatch,
    replies: list[AIMessage],
    saved: list | None = None,
    published: list | None = None,
):
    """The Recruiter Agent with a scripted model and an in-memory checkpointer."""
    model = FakeMessagesListChatModel(responses=replies)
    monkeypatch.setattr(recruiter, "get_agent_model", lambda: model)
    monkeypatch.setitem(
        recruiter.TOOL_HANDLERS, "SaveJob", fake_save_job([] if saved is None else saved)
    )
    monkeypatch.setitem(
        recruiter.TOOL_HANDLERS,
        "PublishJob",
        fake_publish_job([] if published is None else published),
    )
    monkeypatch.setitem(recruiter.PREPARERS, "PublishJob", fake_prepare_publication)
    return recruiter.build_recruiter_graph(InMemorySaver())


def search_call(query: str = "backend engineer python", call_id: str = "search-1") -> AIMessage:
    """A model reply that asks to search the job description references."""
    return AIMessage(
        content="",
        tool_calls=[{"name": "search_jd_references", "args": {"query": query}, "id": call_id}],
    )
