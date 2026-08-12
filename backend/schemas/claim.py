import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field

from models.enums import AdjudicationStatus, ClaimStatus
from schemas.common import JobAccepted


class ClaimSummary(BaseModel):
    """A claim as it appears in a list."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference: str = Field(examples=["CLM-SEED-CAPPED"])
    status: ClaimStatus
    total_billed: float
    total_approved: float | None
    currency: str
    created_at: datetime.datetime


class AuditFindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: AdjudicationStatus
    reason: str
    policy_clause_cited: str | None
    original_clause_text: str | None
    page_number: int | None
    capped_amount: float | None
    confidence: float = Field(
        description="The model's self-reported certainty. Not a calibrated probability."
    )
    chunk_id: uuid.UUID | None = Field(
        default=None, description="The retrieved passage this verdict rests on."
    )


class ClaimItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    line_number: int | None
    category: str
    description: str
    procedure_code: str | None
    billed_amount: float
    allowed_amount: float | None
    audit: AuditFindingOut | None = None


class RiskSignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    title: str
    detail: str
    direction: str
    weight: float = Field(description="Signed points contributed to the aggregate score.")


class RiskScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: float
    band: str
    signal_count: int


class ClaimDetail(ClaimSummary):
    """A claim with everything needed to adjudicate it on one screen."""

    claimant_name: str | None = None
    provider_name: str | None = None
    policy_id: uuid.UUID | None = None
    admission_date: datetime.date | None = None
    discharge_date: datetime.date | None = None
    failure_reason: str | None = None

    items: list[ClaimItemOut] = []
    risk: RiskScoreOut | None = None
    signals: list[RiskSignalOut] = []


class StartAuditRequest(BaseModel):
    policy_id: uuid.UUID = Field(description="The policy to adjudicate this claim against.")


class ClaimCreated(JobAccepted):
    claim_id: uuid.UUID
    reference: str
    document_id: uuid.UUID


class AppealOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    claim_id: uuid.UUID
    content: str
    created_at: datetime.datetime
