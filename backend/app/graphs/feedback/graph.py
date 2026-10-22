"""LangGraph 5: Candidate Feedback Composer (innovation feature F11).

Writes one candidate's email after the decision, checks it for fairness and
sends it only after the interviewer approves it. One run per candidate:

    start -> load_evidence -> (reject: AI email)          -> draft_feedback
                           -> (hire / CV not readable)    -> use_template
                           -> (nothing to write from)     -> handle_error -> end
    draft_feedback -> (answer received)                   -> check_fairness
                   -> (AI not available, first draft)     -> handle_error -> end
                   -> (AI not available, rewriting)       -> human_review
    check_fairness -> (a safety rule broken, attempts left)  -> draft_feedback
                   -> (passed, or last try, or an edit)      -> review_email
    review_email -> (a problem found, attempts left)        -> draft_feedback
                 -> (passed, or last try, or an edit)       -> save_draft
    use_template -> save_draft -> human_review (pauses for the interviewer)
    human_review -> (approve / send anyway) -> send_email
                 -> (edit)                  -> check_fairness, with the new text
                 -> (request changes)       -> draft_feedback, with the note
                 -> (discard)               -> end
    send_email -> (sent)    -> record_sent -> end
               -> (failed)  -> mark_not_sent -> human_review (Try again)

The AI writes freely, in its own words, from the candidate's own points;
nothing about the wording or the number of points is fixed. The checks
guard safety only:
- check_fairness is plain code (fairness.py): no scores, other candidates,
  personal topics, personal data, promises, offer details, quotes or
  placeholders, and no named skill or tool that the candidate's points and
  the job's requirements never mention.
- review_email asks the AI, by meaning: is it kind, does it say anything
  about the candidate their points do not support, is anything unfair?
A problem is sent back for a rewrite (up to 3 tries). Anything left stays
on the draft as a warning naming the words, for the interviewer to fix or
to send anyway after a confirm. Only the backend sends, through the Google
MCP server.
"""

import logging
from functools import lru_cache
from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from app.core.errors import ServiceUnavailableError
from app.core.logging import get_logger, log_event
from app.graphs.base import BaseState, can_retry
from app.graphs.checkpointer import get_checkpointer
from app.graphs.feedback import fairness, store, templates, writing
from app.mcp_clients import client

logger = get_logger(__name__)

NOTHING_TO_WRITE = "This candidate cannot get a feedback email now."
AI_UNAVAILABLE = (
    "The AI service was not available to write the email. Try again in a moment."
)
SEND_FAILED = (
    "The email was not sent: Google could not be reached. Check that the Google "
    "sign-in has not expired, then try again."
)
NO_ADDRESS = "The email was not sent: the candidate has no email address."
GOOGLE_TIMEOUT_SECONDS = 30
NOT_CHECKED = {
    "code": "not_checked",
    "message": "Not checked: the AI review could not run, so read the email yourself",
    "quote": "",
    "words": [],
}

APPROVE = "approve"
SEND_ANYWAY = "send_anyway"
EDIT = "edit"
REQUEST_CHANGES = "request_changes"
DISCARD = "discard"


class FeedbackState(BaseState, total=False):
    candidate_id: int
    # From load_evidence: the email's kind and the facts it may use.
    evidence: dict
    kind: str
    job_id: int
    first_name: str
    written_by: str
    # The email as it stands.
    subject: str
    body: str
    evidence_used: list[dict]
    # What the checks found: problems to fix in a rewrite, warnings kept.
    problems: list[str]
    warnings: list[dict]
    # True while checking text the interviewer wrote: it is never rewritten.
    edited: bool
    # The interviewer's review.
    action: str
    note: str | None
    reviewer_id: int
    revision_failed: bool
    # True once a draft has been saved for review.
    has_draft: bool
    sent: bool
    send_error: str | None
    # Set when no email can be written. The message is safe to show.
    failure: str


def load_evidence(state: FeedbackState) -> dict:
    """Read what the email may be based on: the requirement results of a
    candidate rejected at screening, or the approved report of one
    rejected after the interview."""
    evidence = store.load_evidence(state["candidate_id"])
    if evidence is None:
        return {"failure": NOTHING_TO_WRITE}
    return {
        "evidence": evidence,
        "kind": evidence["kind"],
        "job_id": evidence["job_id"],
        "first_name": evidence["first_name"],
        "subject": templates.subject(evidence["kind"], evidence["job_title"]),
        "attempts": 0,
        "warnings": [],
        "problems": [],
        "edited": False,
    }


def route_after_load(
    state: FeedbackState,
) -> Literal["draft_feedback", "use_template", "handle_error"]:
    if state.get("failure"):
        return "handle_error"
    return "draft_feedback" if state["kind"] in templates.AI_KINDS else "use_template"


def use_template(state: FeedbackState) -> dict:
    """The fixed message for a hire, or for a CV that could not be read.
    No AI call; the interviewer can still edit it."""
    evidence = state["evidence"]
    body = templates.fixed_body(state["kind"], state["first_name"], evidence["job_title"])
    return {"body": body, "written_by": "template", "evidence_used": [], "warnings": []}


def _named(state: FeedbackState, text: str) -> str:
    """The text with the first name taken out again, for the AI."""
    return text.replace(state["first_name"], templates.NAME) if state.get("first_name") else text


def draft_feedback(state: FeedbackState) -> dict:
    """Ask the AI for the email. A request for changes sends the draft and
    the interviewer's note with it; a retry sends what the checks found."""
    attempts = state.get("attempts", 0) + 1
    draft = _named(state, state["body"]) if state.get("note") and state.get("body") else None
    try:
        answer = writing.ask_ai(
            state["evidence"], draft=draft, note=state.get("note"), problems=state.get("problems")
        )
    except ServiceUnavailableError:
        if state.get("has_draft"):
            return {"revision_failed": True, "attempts": attempts}
        return {"failure": AI_UNAVAILABLE, "attempts": attempts}
    return {
        "body": templates.finish(writing.with_greeting(answer.email), state["first_name"]),
        "evidence_used": writing.evidence_used(answer, state["evidence"]),
        "written_by": "ai",
        "problems": [],
        "attempts": attempts,
        "edited": False,
    }


def route_after_draft(
    state: FeedbackState,
) -> Literal["check_fairness", "human_review", "handle_error"]:
    if state.get("failure"):
        return "handle_error"
    if state.get("revision_failed"):
        return "human_review"
    return "check_fairness"


def _known_text(state: FeedbackState) -> str:
    """Everything the email may name: the candidate's points, the job title
    and the job's requirements."""
    evidence = state.get("evidence") or {}
    points = [point["text"] for point in evidence.get("strengths", []) + evidence.get("growth", [])]
    return "\n".join([evidence.get("job_title", ""), evidence.get("requirements", ""), *points])


def _retry_or_keep(state: FeedbackState, found: list[dict], event: str) -> dict:
    """Send an AI draft back with what was found while attempts are left;
    otherwise keep it on the draft as warnings. The interviewer's own text
    is never rewritten."""
    warnings = list(state.get("warnings", []))
    if found and not state.get("edited") and can_retry(state):
        log_event(
            logger,
            event,
            level=logging.WARNING,
            candidate_id=state["candidate_id"],
            attempt=state.get("attempts", 0),
            problems=fairness.codes(found),
        )
        return {"problems": fairness.problem_text(found), "warnings": []}
    return {"warnings": warnings + found, "problems": []}


def check_fairness(state: FeedbackState) -> dict:
    """The safety rules in code (fairness.py), and named skills or tools
    that are not in the candidate's results."""
    known = _known_text(state)
    found = fairness.rule_warnings(state["body"], state.get("first_name", ""), known)
    terms = fairness.unknown_terms(state["body"], state.get("first_name", ""), known)
    if terms:
        found.append(fairness.invented_warning(terms, state["body"]))
    return _retry_or_keep({**state, "warnings": []}, found, "feedback_fairness_failed")


def route_after_check(state: FeedbackState) -> Literal["draft_feedback", "review_email"]:
    return "draft_feedback" if state.get("problems") else "review_email"


def review_email(state: FeedbackState) -> dict:
    """The AI review of meaning: kind and respectful, nothing said about the
    candidate that their points do not support, and nothing unfair. When
    the review cannot run, the draft says so rather than looking checked."""
    try:
        answer = writing.review_email(_named(state, state["body"]), state.get("evidence"))
    except ServiceUnavailableError:
        return {"warnings": list(state.get("warnings", [])) + [NOT_CHECKED], "problems": []}
    body = state["body"]
    found = []
    if answer.unsupported:
        found.append(fairness.invented_warning(answer.unsupported, body))
    if answer.unfair:
        found.append(
            {
                "code": "unfair",
                "message": "May be unfair: "
                + ", ".join(f'"{item}"' for item in answer.unfair[:5]),
                "quote": "",
                "words": answer.unfair[:8],
            }
        )
    if not answer.respectful:
        issue = (answer.tone_issue or "It may sound harsh").strip().rstrip(".")[:160]
        found.append({"code": "tone", "message": f"Tone: {issue}", "quote": "", "words": []})
    # The code check may already have named the same invented words.
    codes = {warning["code"] for warning in state.get("warnings", [])}
    found = [item for item in found if not (item["code"] == "invented" and "invented" in codes)]
    return _retry_or_keep(state, found, "feedback_review_failed")


def route_after_review(state: FeedbackState) -> Literal["draft_feedback", "save_draft"]:
    return "draft_feedback" if state.get("problems") else "save_draft"


def save_draft(state: FeedbackState) -> dict:
    """Keep the email waiting for the interviewer's review."""
    store.save_draft(state["candidate_id"], state)
    log_event(
        logger,
        "feedback_drafted",
        candidate_id=state["candidate_id"],
        kind=state["kind"],
        written_by=state["written_by"],
        warnings=fairness.codes(state.get("warnings", [])),
    )
    return {"has_draft": True}


def human_review(state: FeedbackState) -> dict:
    """Pause until the interviewer approves the email, sends it anyway,
    edits it, asks for changes with a note, or discards it."""
    review = interrupt({"candidate_id": state["candidate_id"]})
    action = review["action"]
    update: dict = {
        "action": action,
        "reviewer_id": review["user_id"],
        "note": review.get("note"),
        "revision_failed": False,
        "send_error": None,
        "problems": [],
    }
    if action == EDIT:
        update.update(
            body=review["body"].strip(),
            subject=(review.get("subject") or state["subject"]).strip(),
            edited=True,
        )
    if action == REQUEST_CHANGES:
        # A rewrite gets a fresh set of attempts.
        update.update(attempts=0, edited=False)
    if action == DISCARD:
        store.discard(state["candidate_id"])
    return update


def route_after_human(
    state: FeedbackState,
) -> Literal["send_email", "check_fairness", "draft_feedback", "__end__"]:
    if state["action"] in (APPROVE, SEND_ANYWAY):
        return "send_email"
    if state["action"] == EDIT:
        return "check_fairness"
    if state["action"] == REQUEST_CHANGES:
        return "draft_feedback"
    return END


def send_email(state: FeedbackState) -> dict:
    """Send the approved email through the Google MCP server. Only the
    backend calls this tool, and only after the interviewer's approval."""
    store.mark_sending(state["candidate_id"], state["reviewer_id"])
    address = store.recipient(state["candidate_id"])
    if not address:
        return {"sent": False, "send_error": NO_ADDRESS}
    try:
        result = client.call_tool(
            "google",
            "send_email",
            {"to": address, "subject": state["subject"], "text": state["body"]},
            timeout=GOOGLE_TIMEOUT_SECONDS,
        )
        if result.is_error:
            raise RuntimeError("send_email reported an error")
    except Exception as exc:
        log_event(
            logger,
            "feedback_send_failed",
            level=logging.WARNING,
            candidate_id=state["candidate_id"],
            error_type=type(exc).__name__,
        )
        return {"sent": False, "send_error": SEND_FAILED}
    return {"sent": True, "send_error": None}


def route_after_send(state: FeedbackState) -> Literal["record_sent", "mark_not_sent"]:
    return "record_sent" if state.get("sent") else "mark_not_sent"


def record_sent(state: FeedbackState) -> dict:
    """Keep that the email was sent, when and by whom; the decision is
    locked from now on."""
    store.record_sent(
        state["candidate_id"], state["reviewer_id"], state["action"] == SEND_ANYWAY
    )
    log_event(
        logger,
        "feedback_sent",
        candidate_id=state["candidate_id"],
        kind=state["kind"],
        sent_anyway=state["action"] == SEND_ANYWAY,
    )
    return {}


def mark_not_sent(state: FeedbackState) -> dict:
    """The email could not be sent. The draft waits for Try again."""
    store.mark_failed(state["candidate_id"], state.get("send_error") or SEND_FAILED)
    return {}


def handle_error(state: FeedbackState) -> dict:
    log_event(
        logger,
        "feedback_not_written",
        level=logging.WARNING,
        candidate_id=state["candidate_id"],
        attempts=state.get("attempts", 0),
    )
    return {"failure": state.get("failure") or AI_UNAVAILABLE}


def build_feedback_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    graph = StateGraph(FeedbackState)
    graph.add_node("load_evidence", load_evidence)
    graph.add_node("use_template", use_template)
    graph.add_node("draft_feedback", draft_feedback)
    graph.add_node("check_fairness", check_fairness)
    graph.add_node("review_email", review_email)
    graph.add_node("save_draft", save_draft)
    graph.add_node("human_review", human_review)
    graph.add_node("send_email", send_email)
    graph.add_node("record_sent", record_sent)
    graph.add_node("mark_not_sent", mark_not_sent)
    graph.add_node("handle_error", handle_error)

    graph.add_edge(START, "load_evidence")
    graph.add_conditional_edges("load_evidence", route_after_load)
    graph.add_edge("use_template", "save_draft")
    graph.add_conditional_edges("draft_feedback", route_after_draft)
    graph.add_conditional_edges("check_fairness", route_after_check)
    graph.add_conditional_edges("review_email", route_after_review)
    graph.add_edge("save_draft", "human_review")
    graph.add_conditional_edges("human_review", route_after_human)
    graph.add_conditional_edges("send_email", route_after_send)
    graph.add_edge("record_sent", END)
    graph.add_edge("mark_not_sent", "human_review")
    graph.add_edge("handle_error", END)
    return graph.compile(checkpointer=checkpointer)


@lru_cache
def get_feedback_graph() -> CompiledStateGraph:
    """The Candidate Feedback graph with PostgreSQL checkpoints, built once."""
    return build_feedback_graph(get_checkpointer())


def thread_id(candidate_id: int) -> str:
    """One thread per candidate. Writing the email again starts it afresh."""
    return f"feedback-{candidate_id}"


def is_waiting_for_review(graph: CompiledStateGraph, config: dict) -> bool:
    return graph.get_state(config).next == ("human_review",)
