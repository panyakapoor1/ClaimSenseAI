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


class RetrievalProvenance(BaseModel):
    """How a passage surfaced.

    Exposed rather than kept internal: without it a caller cannot tell whether a
    result came from semantic similarity, an exact lexical match, or the
    reranker's judgement — which is exactly what is needed to debug a wrong
    citation.
    """

    dense_rank: int | None = Field(description="Rank from embedding search, if found there.")
    lexical_rank: int | None = Field(description="Rank from full-text search, if found there.")
    fusion_score: float = Field(description="Reciprocal rank fusion score.")
    rerank_score: float | None = Field(description="Cross-encoder score, null when not reranked.")


class ClauseMatch(BaseModel):
    """A retrieved policy passage with its provenance."""

    id: uuid.UUID
    section_header: str | None
    text_content: str
    page_number: int | None
    similarity: float = Field(description="Cosine similarity, 1.0 being identical.")
    retrieval: RetrievalProvenance


class ClauseSearchResponse(BaseModel):
    query: str
    results: list[ClauseMatch]
