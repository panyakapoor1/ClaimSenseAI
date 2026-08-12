"""Investigations: the open questions on a claim.

A decision settles something. An investigation is the state of not having settled
it yet — a named person owns a question, with notes accumulating under it until
it is resolved. Keeping that distinct from `human_decisions` means "what is still
open on this claim" is a query rather than an inference from what is absent.
"""

import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.errors import ConflictError, NotFoundError
from models import (
    Claim,
    EventKind,
    Investigation,
    InvestigationNote,
    InvestigationStatus,
    User,
    UserRole,
)
from services import claim_state

OPEN_STATES = {InvestigationStatus.OPEN, InvestigationStatus.IN_PROGRESS}


async def open_investigation(
    session: AsyncSession,
    *,
    claim: Claim,
    actor: User,
    title: str,
    assign_to: User | None = None,
) -> Investigation:
    investigation = Investigation(
        claim_id=claim.id,
        opened_by_id=actor.id,
        assigned_to_id=assign_to.id if assign_to else None,
        title=title.strip(),
        status=InvestigationStatus.IN_PROGRESS if assign_to else InvestigationStatus.OPEN,
    )
    session.add(investigation)

    assigned = f", assigned to {assign_to.full_name or assign_to.email}" if assign_to else ""
    await claim_state.record(
        session,
        claim,
        kind=EventKind.HUMAN_ACTION,
        summary=f"Investigation opened: {title.strip()}{assigned}",
        actor_id=actor.id,
        payload={"assigned_to": str(assign_to.id) if assign_to else None},
    )

    await session.flush()
    return investigation


async def get_investigation(
    session: AsyncSession, claim_id: uuid.UUID, investigation_id: uuid.UUID
) -> Investigation:
    investigation = (
        await session.execute(
            select(Investigation)
            .options(
                selectinload(Investigation.notes).selectinload(InvestigationNote.author),
                selectinload(Investigation.opened_by),
                selectinload(Investigation.assigned_to),
            )
            .where(
                Investigation.id == investigation_id,
                Investigation.claim_id == claim_id,
            )
        )
    ).scalars().first()

    if investigation is None:
        raise NotFoundError(f"No investigation {investigation_id} on this claim.")
    return investigation


async def assign(
    session: AsyncSession,
    *,
    claim: Claim,
    investigation: Investigation,
    actor: User,
    assignee: User,
) -> Investigation:
    if investigation.status not in OPEN_STATES:
        raise ConflictError("This investigation is already resolved.")

    if assignee.role is UserRole.AUDITOR:
        # Auditors are read-only by design; assigning work to one would create an
        # item nobody is permitted to action.
        raise ConflictError(
            "An auditor has read-only access and cannot be assigned an investigation."
        )

    investigation.assigned_to_id = assignee.id
    investigation.status = InvestigationStatus.IN_PROGRESS

    await claim_state.record(
        session,
        claim,
        kind=EventKind.HUMAN_ACTION,
        summary=f"Investigation assigned to {assignee.full_name or assignee.email}",
        detail=investigation.title,
        actor_id=actor.id,
    )
    await session.flush()
    return investigation


async def add_note(
    session: AsyncSession,
    *,
    claim: Claim,
    investigation: Investigation,
    actor: User,
    body: str,
) -> InvestigationNote:
    note = InvestigationNote(
        investigation_id=investigation.id, author_id=actor.id, body=body.strip()
    )
    session.add(note)

    await claim_state.record(
        session,
        claim,
        kind=EventKind.HUMAN_ACTION,
        summary=f"Note added to: {investigation.title}",
        detail=body.strip(),
        actor_id=actor.id,
    )
    await session.flush()
    return note


async def resolve(
    session: AsyncSession,
    *,
    claim: Claim,
    investigation: Investigation,
    actor: User,
    resolution: str,
) -> Investigation:
    if investigation.status not in OPEN_STATES:
        raise ConflictError("This investigation is already resolved.")

    investigation.status = InvestigationStatus.RESOLVED
    investigation.resolution = resolution.strip()
    investigation.closed_at = datetime.datetime.now(datetime.timezone.utc)

    await claim_state.record(
        session,
        claim,
        kind=EventKind.HUMAN_ACTION,
        summary=f"Investigation resolved: {investigation.title}",
        detail=resolution.strip(),
        actor_id=actor.id,
    )
    await session.flush()
    return investigation


async def for_claim(session: AsyncSession, claim_id: uuid.UUID) -> list[Investigation]:
    return list(
        (
            await session.execute(
                select(Investigation)
                .options(
                    selectinload(Investigation.notes).selectinload(InvestigationNote.author),
                    selectinload(Investigation.opened_by),
                    selectinload(Investigation.assigned_to),
                )
                .where(Investigation.claim_id == claim_id)
                .order_by(Investigation.created_at)
            )
        )
        .scalars()
        .all()
    )
