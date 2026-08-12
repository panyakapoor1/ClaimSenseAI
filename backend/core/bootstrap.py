"""Demo tenant bootstrap.

Creates one labelled demo organization and four users — one per role — so the
permission model can actually be exercised. These are real accounts with hashed
passwords behind real authentication, not display-only labels.

The passwords are deliberately well-known and the accounts are clearly named as
demo accounts. That is safe for a demo environment and dishonest to hide: anyone
running this should know these credentials exist. Override the shared password
with DEMO_PASSWORD, or delete these users once real signup exists.

Idempotent: safe to call on every boot.
"""

import datetime
import os
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.security import hash_password
from models import Organization, User, UserRole

DEMO_ORG_SLUG = "demo"
DEMO_ORG_NAME = "ClaimSense Demo"

DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "claimsense-demo")

DEMO_USERS = [
    ("analyst@demo.claimsense.ai", "Demo Analyst", UserRole.ANALYST),
    ("senior@demo.claimsense.ai", "Demo Senior Analyst", UserRole.SENIOR_ANALYST),
    ("admin@demo.claimsense.ai", "Demo Administrator", UserRole.ADMIN),
    ("auditor@demo.claimsense.ai", "Demo Auditor", UserRole.AUDITOR),
]


async def ensure_demo_tenant(session: AsyncSession) -> tuple[Organization, User]:
    """Return the demo organization and its analyst, creating what is missing."""
    org = (
        await session.execute(select(Organization).where(Organization.slug == DEMO_ORG_SLUG))
    ).scalars().first()

    if org is None:
        org = Organization(name=DEMO_ORG_NAME, slug=DEMO_ORG_SLUG)
        session.add(org)
        await session.flush()

    hashed = hash_password(DEMO_PASSWORD)

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
                    hashed_password=hashed,
                )
            )
        else:
            # These are managed accounts, so the table above is authoritative.
            # Reconciling rather than skipping means an account seeded under an
            # earlier role definition is corrected instead of silently keeping a
            # role this code no longer assigns it.
            if existing.hashed_password is None:
                existing.hashed_password = hashed
            if existing.role != role:
                existing.role = role
            if existing.full_name != full_name:
                existing.full_name = full_name

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
