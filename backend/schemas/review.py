import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field

from models.enums import AdjudicationStatus, DecisionAction, InvestigationStatus


class DecisionRequest(BaseModel):
    action: DecisionAction
    claim_item_id: uuid.UUID | None = Field(
        default=None,
        description="Required for actions that settle a specific line item.",
    )
    reason: str = Field(
        default="",
        max_length=4000,
        description=(
            "Required when overriding, rejecting, escalating, confirming fraud or "
            "marking a false positive."
        ),
    )
    override_status: AdjudicationStatus | None = Field(
        default=None,
        description="The verdict an OVERRIDE replaces the AI's with.",
    )


class DecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: DecisionAction
    claim_item_id: uuid.UUID | None
    reason: str
    previous_ai_outcome: str | None = Field(
        description="What the AI had decided before a person intervened."
    )
    overrides_ai: bool = Field(
        description="True when the person's decision differs from the AI's."
    )
    decided_by: str | None
    created_at: datetime.datetime


class CloseClaimRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=4000)


class OpenInvestigationRequest(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    assign_to_id: uuid.UUID | None = None


class AssignRequest(BaseModel):
    assign_to_id: uuid.UUID


class NoteRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class ResolveRequest(BaseModel):
    resolution: str = Field(min_length=1, max_length=4000)


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    body: str
    author: str | None
    created_at: datetime.datetime


class InvestigationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    status: InvestigationStatus
    resolution: str | None
    opened_by: str | None
    assigned_to: str | None
    closed_at: datetime.datetime | None
    created_at: datetime.datetime
    notes: list[NoteOut] = []


class ReviewResponse(BaseModel):
    """Everything a person has done to this claim."""

    claim_id: uuid.UUID
    decisions: list[DecisionOut]
    investigations: list[InvestigationOut]
