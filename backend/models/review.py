from sqlalchemy import Boolean, Column, DateTime, Enum, Index, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base, TimestampMixin, fk, pk
from .enums import DecisionAction, EventKind, InvestigationStatus


class Investigation(Base, TimestampMixin):
    """An open line of enquiry on a claim."""

    __tablename__ = "investigations"

    id = pk()
    claim_id = fk("claims.id")
    opened_by_id = fk("users.id", nullable=True, ondelete="SET NULL")
    assigned_to_id = fk("users.id", nullable=True, ondelete="SET NULL")

    title = Column(String(300), nullable=False)
    status = Column(
        Enum(InvestigationStatus, name="investigation_status", native_enum=True),
        nullable=False,
        server_default=InvestigationStatus.OPEN.value,
        index=True,
    )
    resolution = Column(Text, nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)

    claim = relationship("Claim", back_populates="investigations")
    notes = relationship("InvestigationNote", back_populates="investigation", cascade="all, delete-orphan")
    opened_by = relationship("User", foreign_keys=[opened_by_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])


class InvestigationNote(Base, TimestampMixin):
    __tablename__ = "investigation_notes"

    id = pk()
    investigation_id = fk("investigations.id")
    author_id = fk("users.id", nullable=True, ondelete="SET NULL")
    body = Column(Text, nullable=False)

    investigation = relationship("Investigation", back_populates="notes")
    author = relationship("User")


class HumanDecision(Base, TimestampMixin):
    """What a person decided, and what the AI had said before they decided it.

    Holding `previous_ai_outcome` on the same row is what makes the feedback
    dataset in P11 a join-free query, and what makes disagreement measurable
    rather than anecdotal.
    """

    __tablename__ = "human_decisions"

    id = pk()
    claim_id = fk("claims.id")
    claim_item_id = fk("claim_items.id", nullable=True, ondelete="SET NULL")
    decided_by_id = fk("users.id", nullable=True, ondelete="SET NULL")
    ai_decision_id = fk("ai_decisions.id", nullable=True, ondelete="SET NULL")

    action = Column(Enum(DecisionAction, name="decision_action", native_enum=True), nullable=False)
    reason = Column(Text, nullable=False, server_default="")

    previous_ai_outcome = Column(String(80), nullable=True)
    overrides_ai = Column(Boolean, nullable=False, server_default="false")

    claim = relationship("Claim", back_populates="human_decisions")
    decided_by = relationship("User")


class Event(Base, TimestampMixin):
    """One entry in the unified claim timeline."""

    __tablename__ = "events"
    __table_args__ = (Index("ix_events_claim_occurred", "claim_id", "occurred_at"),)

    id = pk()
    claim_id = fk("claims.id")
    actor_id = fk("users.id", nullable=True, ondelete="SET NULL")

    kind = Column(Enum(EventKind, name="event_kind", native_enum=True), nullable=False)
    summary = Column(String(500), nullable=False)
    detail = Column(Text, nullable=True)

    # Distinct from created_at: when the thing happened, versus when the row was
    # written. Backfilled evidence would otherwise sort to the end of the story.
    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    payload = Column(JSONB, nullable=True)

    claim = relationship("Claim", back_populates="events")
    actor = relationship("User")


class AuditLog(Base):
    """Append-only record of every privileged action.

    Deliberately does not use TimestampMixin: an `updated_at` column on an
    append-only table implies rows can be edited. A database trigger blocks
    UPDATE and DELETE outright, so the guarantee does not depend on every future
    caller remembering it.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_entity", "entity_type", "entity_id"),)

    id = pk()
    actor_id = fk("users.id", nullable=True, ondelete="SET NULL")
    organization_id = fk("organizations.id", nullable=True, ondelete="SET NULL")

    action = Column(String(80), nullable=False, index=True)
    entity_type = Column(String(80), nullable=False)
    entity_id = Column(String(64), nullable=True)

    before = Column(JSONB, nullable=True)
    after = Column(JSONB, nullable=True)

    ip_address = Column(INET, nullable=True)
    user_agent = Column(String(500), nullable=True)
    request_id = Column(String(64), nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
