"""Policy use cases."""

import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import NotFoundError
from models import Document, DocumentKind, Policy, User
from services.claims import store_upload, validate_upload


async def create_policy_from_upload(
    session: AsyncSession,
    *,
    owner: User,
    filename: str,
    content_type: str | None,
    payload: bytes,
    insurer_name: str,
    policy_name: str,
) -> tuple[Policy, Document]:
    validate_upload(filename, content_type, payload)

    storage_key = await store_upload(filename, payload, prefix="policies")

    policy = Policy(
        organization_id=owner.organization_id,
        insurer_name=insurer_name,
        policy_name=policy_name,
    )
    session.add(policy)
    await session.flush()

    document = Document(
        organization_id=owner.organization_id,
        policy_id=policy.id,
        kind=DocumentKind.POLICY,
        filename=filename,
        content_type=content_type or "application/pdf",
        byte_size=len(payload),
        storage_key=storage_key,
        checksum_sha256=hashlib.sha256(payload).hexdigest(),
    )
    session.add(document)
    await session.flush()

    return policy, document


async def list_policies(
    session: AsyncSession, *, organization_id: uuid.UUID
) -> list[Policy]:
    return list(
        (
            await session.execute(
                select(Policy)
                .where(Policy.organization_id == organization_id)
                .order_by(Policy.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def get_policy(
    session: AsyncSession, policy_id: uuid.UUID, *, organization_id: uuid.UUID
) -> Policy:
    """Another organization's policy reports as missing, not forbidden."""
    policy = await session.get(Policy, policy_id)
    if policy is None or policy.organization_id != organization_id:
        raise NotFoundError(f"No policy with id {policy_id}.")
    return policy
