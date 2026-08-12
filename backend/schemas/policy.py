import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field

from schemas.common import JobAccepted


class PolicySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    insurer_name: str
    policy_name: str
    policy_number: str | None
    effective_from: datetime.date | None
    effective_to: datetime.date | None
    sum_insured: float | None
    room_rent_cap: float | None
    created_at: datetime.datetime


class PolicyCreated(JobAccepted):
    policy_id: uuid.UUID
    document_id: uuid.UUID


class ClauseMatch(BaseModel):
    """A retrieved policy passage with its provenance."""

    id: uuid.UUID
    section_header: str | None
    text_content: str
    page_number: int | None
    similarity: float = Field(description="Cosine similarity, 1.0 being identical.")


class ClauseSearchResponse(BaseModel):
    query: str
    results: list[ClauseMatch]
