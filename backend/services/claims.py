"""Claim use cases.

Routes below this line do HTTP; this module does the work. Nothing here imports
FastAPI, so the same functions are callable from the worker, the seed script or
a test without spinning up an app.
"""

import hashlib
import os
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.errors import ConflictError, NotFoundError, ValidationError
from core.bootstrap import ensure_demo_tenant, new_claim_reference
from models import (
    Claim,
    ClaimItem,
    ClaimStatus,
    Document,
    DocumentKind,
    Policy,
    RiskScore,
    RiskSignal,
)
from schemas.common import decode_cursor, encode_cursor

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"application/pdf", "application/octet-stream"}


def validate_upload(filename: str | None, content_type: str | None, payload: bytes) -> None:
    """Reject anything we are not prepared to parse, before it reaches disk.

    The prototype checked only that the filename ended in `.pdf`, so a renamed
    text file reached the worker and crashed the PDF parser with
    "No /Root object!". Checking the magic bytes catches that at the edge.
    """
    if not filename or not filename.lower().endswith(".pdf"):
        raise ValidationError("Only PDF files are supported.")

    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError(f"Unsupported content type: {content_type}")

    if not payload:
        raise ValidationError("The uploaded file is empty.")

    if len(payload) > MAX_UPLOAD_BYTES:
        raise ValidationError(
            f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit."
        )

    if not payload.startswith(b"%PDF-"):
        raise ValidationError(
            "This file is not a PDF. It has a .pdf name but does not contain PDF data."
        )


async def store_upload(filename: str, payload: bytes) -> str:
    """Persist the bytes and return a storage key.

    P4 swaps the local directory for object storage; callers only ever see the
    key, so nothing above this function changes when that happens.
    """
    os.makedirs("uploads", exist_ok=True)
    key = f"uploads/{uuid.uuid4()}_{filename}"
    with open(key, "wb") as fh:
        fh.write(payload)
    return key


async def create_claim_from_bill(
    session: AsyncSession, *, filename: str, content_type: str | None, payload: bytes
) -> tuple[Claim, Document]:
    validate_upload(filename, content_type, payload)

    org, user = await ensure_demo_tenant(session)
    storage_key = await store_upload(filename, payload)

    claim = Claim(
        organization_id=org.id,
        created_by_id=user.id if user else None,
        reference=new_claim_reference(),
        total_billed=0.0,
        status=ClaimStatus.RECEIVED,
    )
    session.add(claim)
    await session.flush()

    document = Document(
        organization_id=org.id,
        claim_id=claim.id,
        kind=DocumentKind.BILL,
        filename=filename,
        content_type=content_type or "application/pdf",
        byte_size=len(payload),
        storage_key=storage_key,
        checksum_sha256=hashlib.sha256(payload).hexdigest(),
    )
    session.add(document)
    await session.flush()

    return claim, document


async def list_claims(
    session: AsyncSession, *, limit: int = 25, cursor: str | None = None
) -> tuple[list[Claim], str | None, bool]:
    """Newest-first page of claims, anchored on (created_at, id)."""
    query = select(Claim).order_by(Claim.created_at.desc(), Claim.id.desc())

    if cursor:
        try:
            created_at, row_id = decode_cursor(cursor)
        except ValueError as e:
            raise ValidationError(str(e)) from e
        # Tuple comparison rather than `created_at <` alone: two claims created in
        # the same millisecond would otherwise straddle the page boundary and one
        # would be skipped.
        query = query.where(
            (Claim.created_at, Claim.id) < (created_at, uuid.UUID(row_id))
        )

    # One extra row tells us whether a further page exists without a COUNT.
    rows = (await session.execute(query.limit(limit + 1))).scalars().all()

    has_more = len(rows) > limit
    items = list(rows[:limit])
    next_cursor = (
        encode_cursor(items[-1].created_at, items[-1].id) if has_more and items else None
    )
    return items, next_cursor, has_more


async def get_claim_detail(session: AsyncSession, claim_id: uuid.UUID) -> Claim:
    """A claim with items, findings, risk and related parties in one round trip."""
    claim = (
        await session.execute(
            select(Claim)
            .options(
                selectinload(Claim.items).selectinload(ClaimItem.audit_finding),
                selectinload(Claim.claimant),
                selectinload(Claim.provider),
                selectinload(Claim.risk_signals),
                selectinload(Claim.risk_scores),
            )
            .where(Claim.id == claim_id)
        )
    ).scalars().first()

    if claim is None:
        raise NotFoundError(f"No claim with id {claim_id}.")
    return claim


def latest_risk_score(claim: Claim) -> RiskScore | None:
    """Risk scores are versioned, so 'the' score is the most recent one."""
    if not claim.risk_scores:
        return None
    return max(claim.risk_scores, key=lambda s: s.created_at)


def sorted_signals(claim: Claim) -> list[RiskSignal]:
    """Heaviest contribution first — that is the order an analyst reads them in."""
    return sorted(claim.risk_signals, key=lambda s: abs(s.weight), reverse=True)


async def assert_auditable(
    session: AsyncSession, claim_id: uuid.UUID, policy_id: uuid.UUID
) -> None:
    """Fail fast before enqueuing an audit that cannot possibly succeed.

    The prototype enqueued unconditionally, so a bad policy id surfaced minutes
    later as a worker traceback and a websocket that closed with no explanation.
    """
    if (await session.get(Claim, claim_id)) is None:
        raise NotFoundError(f"No claim with id {claim_id}.")
    if (await session.get(Policy, policy_id)) is None:
        raise NotFoundError(f"No policy with id {policy_id}.")


async def assert_appealable(session: AsyncSession, claim_id: uuid.UUID) -> Claim:
    claim = await session.get(Claim, claim_id)
    if claim is None:
        raise NotFoundError(f"No claim with id {claim_id}.")
    if claim.status not in (ClaimStatus.AUDIT_COMPLETE, ClaimStatus.APPEAL_GENERATED):
        raise ConflictError(
            f"Claim {claim.reference} is {claim.status.value}; it must be audited "
            "before an appeal can be drafted."
        )
    return claim
