import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, MetaData
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func

# Naming convention so Alembic emits stable, predictable constraint names.
# Without it, autogenerate produces unnamed constraints that later migrations
# cannot reliably drop.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(AsyncAttrs, DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def utcnow() -> datetime.datetime:
    """Timezone-aware UTC.

    The prototype used `datetime.datetime.utcnow`, which is deprecated in 3.12
    and returns a naive datetime, so every stored timestamp silently lost its
    offset and could not be compared against an aware one.
    """
    return datetime.datetime.now(datetime.timezone.utc)


def pk() -> Column:
    """A fresh UUID primary key column.

    A plain factory rather than a mixin: declarative mixins share one Column
    instance across every subclass unless wrapped in `declared_attr`, and calling
    a function per model makes that impossible to get wrong.
    """
    return Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def fk(target: str, *, nullable: bool = False, ondelete: str = "CASCADE") -> Column:
    """A UUID foreign key column with an explicit delete rule."""
    return Column(
        UUID(as_uuid=True),
        ForeignKey(target, ondelete=ondelete),
        nullable=nullable,
        index=True,
    )


class TimestampMixin:
    """created_at / updated_at maintained by the database.

    `server_default` and `onupdate` are used rather than Python defaults so rows
    written outside the ORM (migrations, the seed script, raw SQL) still get
    correct timestamps.
    """

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
