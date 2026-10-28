"""The RAG MCP server: search tools for the Recruiter Agent and the backend.

MCP (Model Context Protocol) is a standard way to offer tools to an AI
agent. This server runs in its own container and speaks MCP over HTTP.
Each tool searches one fixed collection, so the model cannot choose where
to look: job description templates, the interview question bank, or the
reference documents used to check interview answers.

Run with:  python -m app.mcp_servers.rag_server
"""

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger, log_event
from app.rag import store

logger = get_logger(__name__)
settings = get_settings()

MAX_RESULTS = 2
MAX_QUESTIONS = 3
MAX_REFERENCES = 2
# The question and answer are cut to this before they are embedded.
MAX_QUERY_CHARS = 2000
# Questions are searched in a wider pool first, then kept to the role.
QUESTION_POOL = 20

server = MCPServer("HireLucent RAG")


def find_jd_references(query: str) -> list[dict]:
    """Search the uploaded job description templates for close matches."""
    matches = store.search(store.JD_REFERENCES, query, limit=MAX_RESULTS)
    references = [
        {
            "source": match["metadata"]["source"],
            "similarity": round(1 - match["distance"], 2),
            "text": match["text"],
        }
        for match in matches
        if match["distance"] <= settings.jd_reference_max_distance
    ]
    log_event(
        logger, "jd_references_searched", found=len(matches), used=len(references)
    )
    return references


@server.tool()
def search_jd_references(query: str) -> list[dict]:
    """Find existing job description templates similar to a role.

    Use this before writing a job description, with the role and its main
    skills as the query, for example "backend engineer python fastapi".
    Returns up to two templates to use as references for structure and
    style. An empty list means there is no close match, and the description
    should be written from scratch.
    """
    return find_jd_references(query)


def fits_role(roles: str, job_title: str) -> bool:
    """True for a general question file (no roles), or one with a role that
    is part of the job title, so "Backend Engineer" also fits "Senior
    Backend Engineer". Upper and lower case do not matter. A question bank's
    roles are stored as its tags."""
    labels = [role.strip().lower() for role in (roles or "").split(",") if role.strip()]
    title = job_title.strip().lower()
    return not labels or any(label in title for label in labels)


def find_bank_questions(query: str, role: str) -> list[dict]:
    """Search the uploaded interview questions for ones on a topic, from
    the question files for this role and the general ones."""
    matches = store.search(store.QUESTION_BANK, query, limit=QUESTION_POOL)
    questions = [
        {
            "question": match["text"],
            "source": match["metadata"]["source"],
            "similarity": round(1 - match["distance"], 2),
        }
        for match in matches
        if match["distance"] <= settings.question_bank_max_distance
        and fits_role(match["metadata"].get("tags", ""), role)
    ][:MAX_QUESTIONS]
    log_event(logger, "question_bank_searched", found=len(matches), used=len(questions))
    return questions


@server.tool()
def search_question_bank(query: str, role: str = "") -> list[dict]:
    """Find interview questions from the question bank on a topic.

    Use this when the interviewer asks for questions from the question bank,
    with the topic as the query, for example "kubernetes deployments".
    Returns up to three questions, closest first, to quote exactly. An empty
    list means the question bank has nothing on that topic.

    The role is the job title of the interview and is filled in by the
    application: only question files for that role, and general files, are
    searched.
    """
    return find_bank_questions(query, role)


def find_references(question: str, answer: str) -> list[dict]:
    """Search the uploaded reference documents for passages about a question
    and the candidate's answer, closest first."""
    query = f"{question}\n{answer}"[:MAX_QUERY_CHARS]
    matches = store.search(store.RAG_DOCUMENTS, query, limit=MAX_REFERENCES)
    references = [
        {
            "source": match["metadata"]["source"],
            "similarity": round(1 - match["distance"], 2),
            "text": match["text"],
        }
        for match in matches
        if match["distance"] <= settings.reference_max_distance
    ]
    log_event(logger, "references_searched", found=len(matches), used=len(references))
    return references


@server.tool()
def verify_answer(question: str, answer: str) -> list[dict]:
    """Find approved reference passages to check an interview answer against.

    Searches only the Knowledge Base documents uploaded as references.
    Returns up to two passages, closest first, each with its source document.
    An empty list means no reference is close enough, and the answer's
    accuracy can only be judged without one.
    """
    return find_references(question, answer)


if __name__ == "__main__":
    configure_logging(settings)
    server.run(
        "streamable-http",
        host="0.0.0.0",
        port=settings.mcp_rag_port,
        # The server is reachable only from other containers on the private
        # Docker network, which call it by its service name ("mcp-rag").
        # The host check is meant for servers on a developer's own machine.
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        ),
    )
