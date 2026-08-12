from sqlalchemy import Column, Date, Enum, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin, fk, pk
from .enums import AdjudicationStatus, ClaimStatus


class Claimant(Base, TimestampMixin):
    """The patient a claim is filed for.

    Separate from `users`: the person whose treatment is billed is not the person
    operating the software, and conflating them made it impossible to ask "how
    many claims has this patient filed?" — the basis of most frequency signals.
    """

    __tablename__ = "claimants"

    id = pk()
    organization_id = fk("organizations.id")

    full_name = Column(String(200), nullable=False)
    member_id = Column(String(120), nullable=True, index=True)
    date_of_birth = Column(Date, nullable=True)
    email = Column(String(320), nullable=True)
    phone = Column(String(40), nullable=True)

    claims = relationship("Claim", back_populates="claimant")


class Provider(Base, TimestampMixin):
    """A hospital or clinic that issued a bill.

    Its own table because provider identity is a risk signal: repeat appearances
    across unrelated claims are exactly what a frequency rule keys on.
    """

    __tablename__ = "providers"

    id = pk()
    organization_id = fk("organizations.id")

    name = Column(String(300), nullable=False)
    registration_number = Column(String(120), nullable=True, index=True)
    city = Column(String(120), nullable=True)
    address = Column(Text, nullable=True)

    claims = relationship("Claim", back_populates="provider")


class Claim(Base, TimestampMixin):
    __tablename__ = "claims"

    id = pk()
    organization_id = fk("organizations.id")
    created_by_id = fk("users.id", nullable=True, ondelete="SET NULL")
    claimant_id = fk("claimants.id", nullable=True, ondelete="SET NULL")
    provider_id = fk("providers.id", nullable=True, ondelete="SET NULL")
    policy_id = fk("policies.id", nullable=True, ondelete="SET NULL")

    # Human-readable handle. UUIDs are unusable in conversation, and the UI was
    # already reduced to slicing the first eight characters to show anything.
    reference = Column(String(32), nullable=False, unique=True, index=True)

    status = Column(
        Enum(ClaimStatus, name="claim_status", native_enum=True),
        nullable=False,
        server_default=ClaimStatus.RECEIVED.value,
        index=True,
    )

    total_billed = Column(Float, nullable=False, server_default="0")
    total_approved = Column(Float, nullable=True)
    currency = Column(String(3), nullable=False, server_default="INR")

    admission_date = Column(Date, nullable=True)
    discharge_date = Column(Date, nullable=True)

    failure_reason = Column(Text, nullable=True)

    organization = relationship("Organization", back_populates="claims")
    created_by = relationship("User", back_populates="claims")
    claimant = relationship("Claimant", back_populates="claims")
    provider = relationship("Provider", back_populates="claims")
    policy = relationship("Policy", back_populates="claims")

    items = relationship("ClaimItem", back_populates="claim", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="claim")
    facts = relationship("ExtractedFact", back_populates="claim", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="claim", cascade="all, delete-orphan")
    risk_signals = relationship("RiskSignal", back_populates="claim", cascade="all, delete-orphan")
    risk_scores = relationship("RiskScore", back_populates="claim", cascade="all, delete-orphan")
    contradictions = relationship("Contradiction", back_populates="claim", cascade="all, delete-orphan")
    investigations = relationship("Investigation", back_populates="claim", cascade="all, delete-orphan")
    human_decisions = relationship("HumanDecision", back_populates="claim", cascade="all, delete-orphan")
    appeal = relationship("AppealDocument", back_populates="claim", uselist=False, cascade="all, delete-orphan")


class ClaimItem(Base, TimestampMixin):
    """One billed line on the hospital bill."""

    __tablename__ = "claim_items"

    id = pk()
    claim_id = fk("claims.id")

    line_number = Column(Integer, nullable=True)
    category = Column(String(120), nullable=False)
    description = Column(Text, nullable=False)
    procedure_code = Column(String(40), nullable=True, index=True)

    quantity = Column(Float, nullable=True)
    unit_price = Column(Float, nullable=True)
    billed_amount = Column(Float, nullable=False)
    allowed_amount = Column(Float, nullable=True)

    service_date = Column(Date, nullable=True)

    claim = relationship("Claim", back_populates="items")
    audit_finding = relationship(
        "AuditFinding", back_populates="item", uselist=False, cascade="all, delete-orphan"
    )


class AuditFinding(Base, TimestampMixin):
    """The adjudication verdict for a single line item, with its evidence.

    Kept under its existing name rather than renamed to `policy_findings`: it is
    already the per-line coverage decision that name would describe, and a second
    table would have duplicated it.
    """

    __tablename__ = "audit_findings"
    __table_args__ = (
        # Enforced in the database, not just implied by `uselist=False`. Without
        # it a re-audit inserted a second verdict per line and the ORM returned
        # whichever it loaded first.
        UniqueConstraint("claim_item_id", name="uq_audit_findings_claim_item_id"),
    )

    id = pk()
    claim_item_id = fk("claim_items.id")
    model_version_id = fk("model_versions.id", nullable=True, ondelete="SET NULL")

    # Which retrieved passage the verdict actually rested on. This is the link
    # that turns a citation into something clickable in P9.
    chunk_id = fk("document_chunks.id", nullable=True, ondelete="SET NULL")

    status = Column(
        Enum(AdjudicationStatus, name="adjudication_status", native_enum=True), nullable=False
    )
    reason = Column(Text, nullable=False)

    policy_clause_cited = Column(String(500), nullable=True)
    original_clause_text = Column(Text, nullable=True)
    page_number = Column(Integer, nullable=True)

    # Self-reported by the model. Named to keep it distinct from a calibrated
    # probability, which it is not.
    confidence = Column(Float, nullable=False, server_default="0")

    # Amount the policy allows where the item is capped rather than refused.
    capped_amount = Column(Float, nullable=True)

    item = relationship("ClaimItem", back_populates="audit_finding")


class AppealDocument(Base, TimestampMixin):
    __tablename__ = "appeal_documents"

    id = pk()
    claim_id = fk("claims.id")
    model_version_id = fk("model_versions.id", nullable=True, ondelete="SET NULL")
    content = Column(Text, nullable=False)

    claim = relationship("Claim", back_populates="appeal")
