"""Schemas for the Knowledge Base."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

DocumentKind = Literal["jd_template", "reference", "questions"]


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    doc_type: str
    tags: list[str]
    status: str
    chunk_count: int
    created_at: datetime
