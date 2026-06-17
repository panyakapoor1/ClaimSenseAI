from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
import uuid
import datetime
from .base import Base

class Policy(Base):
    __tablename__ = "policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    insurer_name = Column(String, nullable=False)
    policy_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="policies")
    chunks = relationship("PolicyChunk", back_populates="policy", cascade="all, delete-orphan")

class PolicyChunk(Base):
    __tablename__ = "policy_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False)
    page_number = Column(String, nullable=True)
    section_header = Column(String, nullable=True)
    text_content = Column(Text, nullable=False)
    embedding = Column(Vector(384))

    policy = relationship("Policy", back_populates="chunks")
