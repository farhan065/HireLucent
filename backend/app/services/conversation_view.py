"""Turns the saved state of a conversation into what the screen shows.

The conversation is stored as a list of messages. This module reads that
list and builds the timeline (bubbles, notes and cards) and the job brief.
"""

import json
from typing import Any

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage

from app.graphs.recruiter.drafts import draft_in, is_edit
from app.graphs.recruiter.interview_tools import (
    CANCELLED_PREFIX,
    MOVED_PREFIX,
    SCHEDULED_PREFIX,
)
from app.models.enums import ConversationStage
from app.schemas.chat import (
    ConversationView,
    DescriptionBrief,
    JobBrief,
    TimelineItem,
)

NEW_CONVERSATION_TITLE = "New job"
SAVE_TOOL = "SaveJob"
PUBLISH_TOOL = "PublishJob"
SAVED_PREFIX = "Job saved"
PUBLISHED_PREFIX = "Job published at "
REJECTED_PREFIX = "The interviewer did not approve"
SEARCH_TOOL = "search_jd_references"
# Results of the interview tools, each followed by its details as JSON.
INTERVIEW_PREFIXES = (SCHEDULED_PREFIX, MOVED_PREFIX, CANCELLED_PREFIX)
# The card each approval tool is shown as.
CARD_KINDS = {
    SAVE_TOOL: "requirements",
    PUBLISH_TOOL: "post",
    "ScheduleInterviews": "schedule",
    "RescheduleInterview": "reschedule",
    "CancelInterview": "cancel_interview",
}


def build_view(
    thread_id: str,
    values: dict[str, Any],
    pending: dict[str, Any] | None,
    job_code: str | None,
) -> ConversationView:
    """Build the full view of one conversation from its saved state.

    pending is the action waiting for approval, if any, with its details
    already checked and completed.
    """
    messages: list[AnyMessage] = values.get("messages", [])
    items = _timeline(messages)
    is_waiting = pending is not None
    if pending is not None and items and items[-1].kind in CARD_KINDS.values():
        items[-1].arguments = pending["arguments"]
    descriptions = [item for item in items if item.kind == "description"]
    requirement_cards = [item for item in items if item.kind == "requirements"]
    published = next((item for item in items if item.kind == "published"), None)
    job_id = values.get("saved_job_id")

    if published:
        stage = ConversationStage.PUBLISHED
    elif is_waiting and pending["action"] == PUBLISH_TOOL:
        stage = ConversationStage.CONFIRMING_POST
    elif job_id:
        stage = ConversationStage.SAVED
    elif is_waiting:
        stage = ConversationStage.CONFIRMING_REQUIREMENTS
    elif descriptions:
        stage = ConversationStage.REVIEWING_DESCRIPTION
    else:
        stage = ConversationStage.DESCRIBING

    brief = JobBrief(job_id=job_id, job_code=job_code)
    if published:
        approved_post = next(
            item for item in items if item.kind == "post" and item.status == "approved"
        )
        brief.post_url = published.text
        brief.form_url = (approved_post.arguments or {}).get("form_url")
    if descriptions:
        latest = descriptions[-1]
        brief.description = DescriptionBrief(
            version=latest.version or 1,
            title=latest.title or "",
            text=latest.text,
            status=latest.status or "waiting",
        )
    current = next(
        (
            card
            for card in reversed(requirement_cards)
            if card.status in ("waiting", "approved")
        ),
        None,
    )
    if current is not None and current.arguments:
        brief.requirements = current.arguments.get("requirements")
        brief.scoring_weights = current.arguments.get("scoring_weights")
        brief.requirements_status = (
            "confirmed" if current.status == "approved" else "proposed"
        )

    return ConversationView(
        thread_id=thread_id,
        title=_title(messages, descriptions),
        stage=stage,
        items=items,
        brief=brief,
    )


def _timeline(messages: list[AnyMessage]) -> list[TimelineItem]:
    """Walk the messages in order and turn each into bubbles, notes or cards."""
    outcomes = _tool_outcomes(messages)
    results = {
        message.tool_call_id: message.text
        for message in messages
        if isinstance(message, ToolMessage)
    }
    items: list[TimelineItem] = []
    version = 0
    # True from the first search that found a template. Every draft after
    # it is built on that template, so each one shows the source.
    used_template = False

    for index, message in enumerate(messages):
        item_id = message.id or f"m{index}"
        draft = draft_in(message)

        if is_edit(message) and draft is not None:
            version += 1
            items.append(
                TimelineItem(
                    id=f"{item_id}-note",
                    kind="note",
                    text=f"You edited the job description. Saved as draft {version}.",
                )
            )
            items.append(_description_item(item_id, draft, version, used_template))
        elif isinstance(message, HumanMessage):
            items.append(TimelineItem(id=item_id, kind="user", text=message.text))
        elif isinstance(message, AIMessage):
            if draft is not None:
                version += 1
                if draft.preamble:
                    items.append(
                        TimelineItem(
                            id=f"{item_id}-intro", kind="assistant", text=draft.preamble
                        )
                    )
                items.append(_description_item(item_id, draft, version, used_template))
            elif message.text.strip():
                items.append(
                    TimelineItem(id=item_id, kind="assistant", text=message.text)
                )
            for call in message.tool_calls:
                if call["name"] not in CARD_KINDS:
                    if call["name"] == SEARCH_TOOL:
                        used_template = used_template or _found_template(
                            results.get(call["id"])
                        )
                    continue
                status = outcomes.get(call["id"], "waiting")
                if status == "invalid":
                    continue
                items.append(
                    TimelineItem(
                        id=call["id"],
                        kind=CARD_KINDS[call["name"]],
                        status=status,
                        arguments=call["args"],
                    )
                )
                result = results.get(call["id"], "")
                if result.startswith(INTERVIEW_PREFIXES):
                    items[-1].result = json.loads(result.split(": ", 1)[1])
                if result.startswith(PUBLISHED_PREFIX):
                    items.append(
                        TimelineItem(
                            id=f"{call['id']}-live",
                            kind="published",
                            text=result.removeprefix(PUBLISHED_PREFIX),
                        )
                    )

    _mark_description_status(items)
    return items


def _found_template(result: str | None) -> bool:
    """True if a Knowledge Base search returned at least one template."""
    try:
        return bool(json.loads(result or ""))
    except ValueError:
        return False


def _description_item(
    item_id: str, draft: Any, version: int, from_knowledge_base: bool
) -> TimelineItem:
    return TimelineItem(
        id=item_id,
        kind="description",
        title=draft.title,
        text=draft.body,
        version=version,
        from_knowledge_base=from_knowledge_base,
        status="waiting",
    )


def _tool_outcomes(messages: list[AnyMessage]) -> dict[str, str]:
    """What happened to each approval request: approved, changed or invalid."""
    outcomes: dict[str, str] = {}
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        text = message.text
        if text.startswith((SAVED_PREFIX, PUBLISHED_PREFIX, *INTERVIEW_PREFIXES)):
            outcomes[message.tool_call_id] = "approved"
        elif text.startswith(REJECTED_PREFIX):
            outcomes[message.tool_call_id] = "changed"
        else:
            outcomes[message.tool_call_id] = "invalid"
    return outcomes


def _mark_description_status(items: list[TimelineItem]) -> None:
    """Older drafts are replaced. The newest is approved once the
    conversation has moved on to the requirements."""
    last_description = None
    for index, item in enumerate(items):
        if item.kind == "description":
            if last_description is not None:
                items[last_description].status = "replaced"
            last_description = index
    if last_description is None:
        return
    moved_on = any(
        item.kind == "requirements" and item.status in ("waiting", "approved")
        for item in items[last_description + 1 :]
    )
    items[last_description].status = "approved" if moved_on else "waiting"


def _title(messages: list[AnyMessage], descriptions: list[TimelineItem]) -> str:
    """The job title once there is a draft, otherwise the first message."""
    if descriptions:
        return descriptions[-1].title or NEW_CONVERSATION_TITLE
    for message in messages:
        if isinstance(message, HumanMessage):
            text = " ".join(message.text.split())
            return text[:60] + ("…" if len(text) > 60 else "")
    return NEW_CONVERSATION_TITLE
