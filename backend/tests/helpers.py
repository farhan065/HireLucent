"""Building blocks shared by the Recruiter Agent and chat tests."""

from langchain_core.language_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.graphs.recruiter import graph as recruiter

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


def graph_with_replies(monkeypatch, replies: list[AIMessage], saved: list | None = None):
    """The Recruiter Agent with a scripted model and an in-memory checkpointer."""
    model = FakeMessagesListChatModel(responses=replies)
    monkeypatch.setattr(recruiter, "get_agent_model", lambda: model)
    monkeypatch.setitem(
        recruiter.TOOL_HANDLERS, "SaveJob", fake_save_job([] if saved is None else saved)
    )
    return recruiter.build_recruiter_graph(InMemorySaver())


def search_call(query: str = "backend engineer python", call_id: str = "search-1") -> AIMessage:
    """A model reply that asks to search the job description references."""
    return AIMessage(
        content="",
        tool_calls=[{"name": "search_jd_references", "args": {"query": query}, "id": call_id}],
    )
