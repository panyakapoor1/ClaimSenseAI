from sqlalchemy import Boolean, Column, Enum, String
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin, fk, pk
from .enums import UserRole


class Organization(Base, TimestampMixin):
    """The tenant that owns claims, policies and documents.

    Introduced so ownership is a real column rather than an assumption. The
    prototype seeded one user and attached every claim to it, which meant no
    query could ever be scoped and "whose claim is this?" had no answer.
    """

    __tablename__ = "organizations"

    id = pk()
    name = Column(String(200), nullable=False)
    slug = Column(String(80), nullable=False, unique=True, index=True)

    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    claims = relationship("Claim", back_populates="organization")
    policies = relationship("Policy", back_populates="organization")


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = pk()
    organization_id = fk("organizations.id")
    email = Column(String(320), unique=True, index=True, nullable=False)
    full_name = Column(String(200), nullable=False, server_default="")

    # Nullable until P3 introduces real credentials. Left explicit rather than
    # defaulted to an empty string so "has no password yet" stays distinguishable
    # from "password is blank".
    hashed_password = Column(String(255), nullable=True)

    role = Column(
        Enum(UserRole, name="user_role", native_enum=True),
        nullable=False,
        server_default=UserRole.ANALYST.value,
    )
    is_active = Column(Boolean, nullable=False, server_default="true")

    organization = relationship("Organization", back_populates="users")
    claims = relationship("Claim", back_populates="created_by")
