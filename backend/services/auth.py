"""Authentication and authorisation rules.

The permission model lives here as data rather than as scattered `if` statements,
so "who can do what" is one readable table and the test matrix can assert
against the same source the app enforces.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import ForbiddenError, UnauthenticatedError
from core.security import create_access_token, verify_password
from models import User, UserRole

# Capabilities, named for what a person does rather than for an HTTP route.
READ_CLAIMS = "claims:read"
CREATE_CLAIMS = "claims:create"
RUN_ANALYSIS = "claims:analyse"
DECIDE_CLAIMS = "claims:decide"
MANAGE_POLICIES = "policies:manage"
ADMINISTER = "system:administer"

# Opening investigations, leaving notes, escalating. Distinct from DECIDE_CLAIMS:
# raising a concern is not the same authority as settling one, and an analyst
# needs the first without the second.
INVESTIGATE = "claims:investigate"

ROLE_CAPABILITIES: dict[UserRole, set[str]] = {
    # Investigates claims: can run the pipeline, cannot make final decisions.
    UserRole.ANALYST: {
        READ_CLAIMS, CREATE_CLAIMS, RUN_ANALYSIS, MANAGE_POLICIES, INVESTIGATE,
    },
    # Everything an analyst can do, plus approving and escalating.
    UserRole.SENIOR_ANALYST: {
        READ_CLAIMS, CREATE_CLAIMS, RUN_ANALYSIS, MANAGE_POLICIES, INVESTIGATE,
        DECIDE_CLAIMS,
    },
    # Manages the system. Deliberately not granted DECIDE_CLAIMS: administering
    # the platform is not the same job as adjudicating a patient's claim, and
    # conflating them is how audit trails stop meaning anything.
    UserRole.ADMIN: {
        READ_CLAIMS, CREATE_CLAIMS, RUN_ANALYSIS, MANAGE_POLICIES, ADMINISTER,
    },
    # Read-only oversight. Sees everything, changes nothing.
    UserRole.AUDITOR: {READ_CLAIMS},
}


def capabilities_for(role: UserRole) -> set[str]:
    return ROLE_CAPABILITIES.get(role, set())


def can(role: UserRole, capability: str) -> bool:
    return capability in capabilities_for(role)


def require_capability(role: UserRole, capability: str) -> None:
    if not can(role, capability):
        raise ForbiddenError(
            f"Role {role.value} is not permitted to {capability.replace(':', ' ')}."
        )


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    """Verify credentials.

    The same error is returned whether the address is unknown or the password is
    wrong, so the endpoint cannot be used to discover which addresses exist. The
    hash is verified even for a missing user to keep the timing comparable.
    """
    user = (
        await session.execute(select(User).where(User.email == email.strip().lower()))
    ).scalars().first()

    hashed = user.hashed_password if user else None
    if not verify_password(password, hashed):
        raise UnauthenticatedError("Incorrect email or password.")

    if not user.is_active:
        raise UnauthenticatedError("This account has been deactivated.")

    return user


def issue_token(user: User) -> tuple[str, int]:
    return create_access_token(
        user_id=str(user.id),
        organization_id=str(user.organization_id),
        role=user.role.value,
    )


async def load_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    """Re-read the user named by a token.

    The token carries a role, but a deactivated account must stop working before
    its token expires, so the account itself is checked on every request.
    """
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise UnauthenticatedError("This session is no longer valid.")
    return user
