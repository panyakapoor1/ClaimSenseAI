from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import datetime
from .base import Base

class Claim(Base):
    __tablename__ = "claims"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    total_billed = Column(Float, nullable=False)
    status = Column(String, default="PENDING")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="claims")
    items = relationship("ClaimItem", back_populates="claim", cascade="all, delete-orphan")
    appeal = relationship("AppealDocument", back_populates="claim", uselist=False, cascade="all, delete-orphan")

class ClaimItem(Base):
    __tablename__ = "claim_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id = Column(UUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False)
    category = Column(String, nullable=False)
    description = Column(String, nullable=False)
    billed_amount = Column(Float, nullable=False)
    allowed_amount = Column(Float, nullable=True)

    claim = relationship("Claim", back_populates="items")
    audit_finding = relationship("AuditFinding", back_populates="item", uselist=False, cascade="all, delete-orphan")

class AuditFinding(Base):
    __tablename__ = "audit_findings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_item_id = Column(UUID(as_uuid=True), ForeignKey("claim_items.id", ondelete="CASCADE"), nullable=False, unique=True)
    status = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    policy_clause_cited = Column(String, nullable=True)
    original_clause_text = Column(String, nullable=True)
    page_number = Column(String, nullable=True)
    confidence = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    item = relationship("ClaimItem", back_populates="audit_finding")

class AppealDocument(Base):
    __tablename__ = "appeal_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id = Column(UUID(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, unique=True)
    content = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    claim = relationship("Claim", back_populates="appeal")
