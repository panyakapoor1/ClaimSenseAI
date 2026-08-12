"""Claim use cases.

Routes below this line do HTTP; this module does the work. Nothing here imports
FastAPI, so the same functions are callable from the worker, the seed script or
a test without spinning up an app.
"""

import asyncio
import hashlib
import os
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.errors import ConflictError, NotFoundError, ValidationError
from core.bootstrap import new_claim_reference
from models import (
    Claim,
    ClaimItem,
    ClaimStatus,
    Document,
    DocumentKind,
    Policy,
    RiskScore,
    RiskSignal,
    User,
)
from schemas.common import decode_cursor, encode_cursor
from services import storage

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


async def store_upload(filename: str, payload: bytes, *, prefix: str) -> str:
    """Persist the bytes durably and return the storage key.

    Documents are kept, not deleted after parsing: a finding that cites page 4 is
    worthless if page 4 no longer exists. Written through the storage service so
    the same call works against MinIO, S3, or the local filesystem fallback.
    """
    safe_name = os.path.basename(filename).replace("/", "_")
    key = f"{prefix}/{uuid.uuid4()}/{safe_name}"
    return await asyncio.to_thread(storage.put, key, payload)


async def create_claim_from_bill(
    session: AsyncSession,
    *,
    owner: User,
    filename: str,
    content_type: str | None,
    payload: bytes,
) -> tuple[Claim, Document]:
    validate_upload(filename, content_type, payload)

    storage_key = await store_upload(filename, payload, prefix="bills")

    claim = Claim(
        organization_id=owner.organization_id,
        created_by_id=owner.id,
        reference=new_claim_reference(),
        total_billed=0.0,
        status=ClaimStatus.RECEIVED,
    )
    session.add(claim)
    await session.flush()

    document = Document(
        organization_id=owner.organization_id,
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
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    limit: int = 25,
    cursor: str | None = None,
) -> tuple[list[Claim], str | None, bool]:
    """Newest-first page of claims belonging to one organization.

    The organization filter is a required argument rather than an optional one:
    a caller cannot forget to scope the query, because there is no unscoped form
    of this function to call by accident.
    """
    query = (
        select(Claim)
        .where(Claim.organization_id == organization_id)
        .order_by(Claim.created_at.desc(), Claim.id.desc())
    )

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


async def get_claim_detail(
    session: AsyncSession, claim_id: uuid.UUID, *, organization_id: uuid.UUID
) -> Claim:
    """A claim with items, findings, risk and related parties in one round trip.

    A claim owned by another organization reports as missing rather than
    forbidden: answering 403 would confirm the id exists, letting an outsider
    enumerate which claims are real.
    """
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
            .where(Claim.id == claim_id, Claim.organization_id == organization_id)
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
    session: AsyncSession,
    claim_id: uuid.UUID,
    policy_id: uuid.UUID,
    *,
    organization_id: uuid.UUID,
) -> None:
    """Fail fast before enqueuing an audit that cannot possibly succeed.

    The prototype enqueued unconditionally, so a bad policy id surfaced minutes
    later as a worker traceback and a websocket that closed with no explanation.
    """
    claim = await session.get(Claim, claim_id)
    if claim is None or claim.organization_id != organization_id:
        raise NotFoundError(f"No claim with id {claim_id}.")

    policy = await session.get(Policy, policy_id)
    if policy is None or policy.organization_id != organization_id:
        raise NotFoundError(f"No policy with id {policy_id}.")


async def assert_appealable(
    session: AsyncSession, claim_id: uuid.UUID, *, organization_id: uuid.UUID
) -> Claim:
    claim = await session.get(Claim, claim_id)
    if claim is None or claim.organization_id != organization_id:
        raise NotFoundError(f"No claim with id {claim_id}.")
    if claim.status not in (ClaimStatus.AUDIT_COMPLETE, ClaimStatus.APPEAL_GENERATED):
        raise ConflictError(
            f"Claim {claim.reference} is {claim.status.value}; it must be audited "
            "before an appeal can be drafted."
        )
    return claim
