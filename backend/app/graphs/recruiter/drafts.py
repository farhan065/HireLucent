"""Finds job description drafts in a conversation.

A draft is a message whose text contains a line starting with "# ", the job
title. It can come from the assistant, or from the interviewer when they
edit the description directly.
"""

from dataclasses import dataclass

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage

EDIT_KIND = "description_edit"


@dataclass(frozen=True)
class Draft:
    title: str
    body: str
    # Anything the assistant wrote before the heading, shown as a normal reply.
    preamble: str = ""

    @property
    def markdown(self) -> str:
        return f"# {self.title}\n\n{self.body}".strip()


def parse_draft(text: str) -> Draft | None:
    """Split a message into preamble, title and body, or return None."""
    lines = text.strip().splitlines()
    for index, line in enumerate(lines):
        if line.startswith("# ") and line[2:].strip():
            return Draft(
                title=line[2:].strip(),
                body="\n".join(lines[index + 1 :]).strip(),
                preamble="\n".join(lines[:index]).strip(),
            )
    return None


def is_edit(message: AnyMessage) -> bool:
    """True for a description the interviewer edited directly."""
    return (
        isinstance(message, HumanMessage)
        and message.additional_kwargs.get("kind") == EDIT_KIND
    )


def draft_in(message: AnyMessage) -> Draft | None:
    """The draft a message contains, if any."""
    if isinstance(message, AIMessage) or is_edit(message):
        return parse_draft(message.text)
    return None


def latest_draft(messages: list[AnyMessage]) -> Draft | None:
    """The newest description in the conversation."""
    for message in reversed(messages):
        draft = draft_in(message)
        if draft is not None:
            return draft
    return None
