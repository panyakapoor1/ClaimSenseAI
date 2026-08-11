from sqlalchemy import Boolean, Column, Enum, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin, fk, pk
from .enums import RiskBand, SignalDirection


class ModelVersion(Base, TimestampMixin):
    """A pinned version of something that produces AI output.

    Every AI-written row references one of these. Without it, a finding produced
    by a model that has since been retired is indistinguishable from a current
    one — which is precisely the situation the Groq deprecations created.
    """

    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("kind", "identifier", name="uq_model_versions_kind_identifier"),)

    id = pk()

    # e.g. "llm", "embedding", "reranker", "risk_model"
    kind = Column(String(40), nullable=False)
    identifier = Column(String(200), nullable=False)
    provider = Column(String(80), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")

    notes = Column(Text, nullable=True)


class RiskSignal(Base, TimestampMixin):
    """One rule that fired, with the weight it contributed and why.

    Rows here are what a risk score decomposes into. A score with no signals
    behind it is a number nobody can argue with, which is the failure mode the
    whole engine exists to avoid.
    """

    __tablename__ = "risk_signals"

    id = pk()
    claim_id = fk("claims.id")
    claim_item_id = fk("claim_items.id", nullable=True, ondelete="SET NULL")

    # Stable rule identifier, e.g. "DUPLICATE_LINE_ITEM", "ROOM_RENT_CAP_BREACH".
    code = Column(String(80), nullable=False, index=True)
    title = Column(String(300), nullable=False)
    detail = Column(Text, nullable=False, server_default="")

    direction = Column(
        Enum(SignalDirection, name="signal_direction", native_enum=True),
        nullable=False,
        server_default=SignalDirection.AGGRAVATING.value,
    )

    # Signed points contributed to the aggregate score.
    weight = Column(Float, nullable=False, server_default="0")

    # Which facts / chunks / items justify this signal, so the UI can highlight
    # them when the row is hovered.
    evidence_refs = Column(JSONB, nullable=True)

    claim = relationship("Claim", back_populates="risk_signals")


class RiskScore(Base, TimestampMixin):
    """An aggregate score for a claim at a point in time.

    Versioned rather than overwritten: re-scoring after new evidence arrives
    should be visible as a change, not erase what the analyst saw earlier.
    """

    __tablename__ = "risk_scores"

    id = pk()
    claim_id = fk("claims.id")
    model_version_id = fk("model_versions.id", nullable=True, ondelete="SET NULL")

    score = Column(Float, nullable=False)
    band = Column(Enum(RiskBand, name="risk_band", native_enum=True), nullable=False)
    signal_count = Column(Integer, nullable=False, server_default="0")

    # Per-signal contributions frozen at scoring time, so the breakdown shown to
    # an analyst stays reproducible even after the rules are retuned.
    breakdown = Column(JSONB, nullable=True)

    claim = relationship("Claim", back_populates="risk_scores")


class Contradiction(Base, TimestampMixin):
    """Two pieces of evidence that cannot both be true."""

    __tablename__ = "contradictions"

    id = pk()
    claim_id = fk("claims.id")

    left_fact_id = fk("extracted_facts.id", nullable=True, ondelete="SET NULL")
    right_fact_id = fk("extracted_facts.id", nullable=True, ondelete="SET NULL")

    summary = Column(String(500), nullable=False)
    detail = Column(Text, nullable=False, server_default="")
    # Shares the risk_band type with RiskScore. The migration creates the type
    # once explicitly; `create_type` is not a valid argument on the generic
    # Enum, so type creation must not be inferred from either column.
    severity = Column(Enum(RiskBand, name="risk_band", native_enum=True), nullable=False)

    claim = relationship("Claim", back_populates="contradictions")


class AIDecision(Base, TimestampMixin):
    """An AI-produced conclusion, stamped so it can be audited or overridden.

    Deliberately generic: adjudications, risk calls and copilot answers all land
    here, so "what did the model say, when, and with which version" is one query.
    """

    __tablename__ = "ai_decisions"

    id = pk()
    claim_id = fk("claims.id")
    model_version_id = fk("model_versions.id", nullable=True, ondelete="SET NULL")

    # e.g. "ADJUDICATION", "RISK", "APPEAL", "COPILOT"
    decision_type = Column(String(40), nullable=False, index=True)
    subject_id = Column(String(64), nullable=True)

    outcome = Column(String(80), nullable=False)
    rationale = Column(Text, nullable=False, server_default="")
    confidence = Column(Float, nullable=True)

    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)

    citations = Column(JSONB, nullable=True)
