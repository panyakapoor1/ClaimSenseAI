"""Demo tenant bootstrap.

Until P3 introduces real authentication there is no authenticated principal to
attribute work to, but the schema now requires one. This module creates a single
labelled demo organization and its two demo users — the same two the login page
offers — so that ownership columns hold real rows rather than a placeholder.

Idempotent: safe to call on every boot.
"""

import datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from models import Organization, User, UserRole

DEMO_ORG_SLUG = "demo"
DEMO_ORG_NAME = "ClaimSense Demo"

DEMO_USERS = [
    ("auditor@demo.claimsense.ai", "Demo Auditor", UserRole.ANALYST),
    ("admin@demo.claimsense.ai", "Demo Administrator", UserRole.ADMIN),
]


async def ensure_demo_tenant(session: AsyncSession) -> tuple[Organization, User]:
    """Return the demo organization and its analyst user, creating them if absent."""
    org = (
        await session.execute(select(Organization).where(Organization.slug == DEMO_ORG_SLUG))
    ).scalars().first()

    if org is None:
        org = Organization(name=DEMO_ORG_NAME, slug=DEMO_ORG_SLUG)
        session.add(org)
        await session.flush()

    for email, full_name, role in DEMO_USERS:
        existing = (
            await session.execute(select(User).where(User.email == email))
        ).scalars().first()
        if existing is None:
            session.add(
                User(
                    organization_id=org.id,
                    email=email,
                    full_name=full_name,
                    role=role,
                )
            )

    await session.flush()

    analyst = (
        await session.execute(
            select(User)
            .where(User.organization_id == org.id, User.role == UserRole.ANALYST)
            .order_by(User.created_at)
        )
    ).scalars().first()

    return org, analyst


def new_claim_reference() -> str:
    """A short, human-quotable claim reference.

    Random rather than sequential: a monotonic counter would need a lock to stay
    correct under concurrent uploads, and the reference carries no meaning beyond
    identity. The unique index is the actual guarantee.
    """
    year = datetime.datetime.now(datetime.timezone.utc).year
    return f"CLM-{year}-{uuid.uuid4().hex[:6].upper()}"
