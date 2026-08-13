from sqlalchemy import Column, Date, Float, String
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin, fk, pk


class Policy(Base, TimestampMixin):
    __tablename__ = "policies"

    id = pk()
    organization_id = fk("organizations.id")

    insurer_name = Column(String(300), nullable=False)
    policy_name = Column(String(300), nullable=False)
    policy_number = Column(String(120), nullable=True, index=True)

    # Coverage window. Policy timing is a standard risk signal: treatment dated
    # outside the window, or a claim filed suspiciously soon after inception.
    effective_from = Column(Date, nullable=True)
    effective_to = Column(Date, nullable=True)

    sum_insured = Column(Float, nullable=True)
    room_rent_cap = Column(Float, nullable=True)

    organization = relationship("Organization", back_populates="policies")
    claims = relationship("Claim", back_populates="policy")
    documents = relationship("Document", back_populates="policy")
    chunks = relationship("DocumentChunk", back_populates="policy")
