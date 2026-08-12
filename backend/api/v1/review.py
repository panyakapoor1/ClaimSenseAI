"""Human review: decisions and investigations.

Authorisation is per action rather than per route. Raising a concern
(INVESTIGATE) and settling one (DECIDE_CLAIMS) are different authorities, so a
single "can touch this claim" permission would be too coarse — an analyst needs
to escalate without being able to approve.

Every action writes an audit_logs entry. That table is append-only at the
database level, so the record of who did what cannot be edited afterwards, even
by this code.
"""

import uuid

from fastapi import APIRouter, Request, status

from api.deps import CurrentUser, SessionDep, requires
from api.errors import ForbiddenError, NotFoundError
from models import DecisionAction, User
from schemas.review import (
    AssignRequest,
    CloseClaimRequest,
    DecisionOut,
    DecisionRequest,
    InvestigationOut,
    NoteOut,
    NoteRequest,
    OpenInvestigationRequest,
    ResolveRequest,
    ReviewResponse,
)
from services import auth as auth_service
from services import claims as claim_service
from services import decisions as decision_service
from services import investigations as investigation_service
from services.audit import record_audit

router = APIRouter(prefix="/claims", tags=["review"])

# Which capability each action demands. Settling a line item is a senior
# decision; raising a question about one is not.
ACTION_CAPABILITY = {
    DecisionAction.APPROVE: auth_service.DECIDE_CLAIMS,
    DecisionAction.REJECT: auth_service.DECIDE_CLAIMS,
    DecisionAction.OVERRIDE: auth_service.DECIDE_CLAIMS,
    DecisionAction.CONFIRM_FRAUD: auth_service.DECIDE_CLAIMS,
    DecisionAction.MARK_FALSE_POSITIVE: auth_service.DECIDE_CLAIMS,
    DecisionAction.ESCALATE: auth_service.INVESTIGATE,
    DecisionAction.REQUEST_EVIDENCE: auth_service.INVESTIGATE,
}


def _present_decision(decision) -> DecisionOut:
    return DecisionOut(
        id=decision.id,
        action=decision.action,
        claim_item_id=decision.claim_item_id,
        reason=decision.reason,
        previous_ai_outcome=decision.previous_ai_outcome,
        overrides_ai=decision.overrides_ai,
        decided_by=(
            decision.decided_by.full_name or decision.decided_by.email
            if decision.decided_by else None
        ),
        created_at=decision.created_at,
    )


def _present_investigation(investigation) -> InvestigationOut:
    return InvestigationOut(
        id=investigation.id,
        title=investigation.title,
        status=investigation.status,
        resolution=investigation.resolution,
        opened_by=(
            investigation.opened_by.full_name or investigation.opened_by.email
            if investigation.opened_by else None
        ),
        assigned_to=(
            investigation.assigned_to.full_name or investigation.assigned_to.email
            if investigation.assigned_to else None
        ),
        closed_at=investigation.closed_at,
        created_at=investigation.created_at,
        notes=[
            NoteOut(
                id=n.id,
                body=n.body,
                author=(n.author.full_name or n.author.email) if n.author else None,
                created_at=n.created_at,
            )
            for n in sorted(investigation.notes, key=lambda n: n.created_at)
        ],
    )


async def _assignee(session, user: User, assignee_id: uuid.UUID) -> User:
    """Resolve an assignee, scoped to the caller's organization."""
    candidate = await session.get(User, assignee_id)
    if candidate is None or candidate.organization_id != user.organization_id:
        raise NotFoundError(f"No user {assignee_id} in your organization.")
    return candidate


@router.get(
    "/{claim_id}/review",
    response_model=ReviewResponse,
    summary="Human decisions and investigations on a claim",
)
async def get_review(
    claim_id: uuid.UUID,
    session: SessionDep,
    user: User = requires(auth_service.READ_CLAIMS),
):
    await claim_service.get_claim_detail(
        session, claim_id, organization_id=user.organization_id
    )

    return ReviewResponse(
        claim_id=claim_id,
        decisions=[
            _present_decision(d)
            for d in await decision_service.decisions_for_claim(session, claim_id)
        ],
        investigations=[
            _present_investigation(i)
            for i in await investigation_service.for_claim(session, claim_id)
        ],
    )


@router.post(
    "/{claim_id}/decisions",
    response_model=DecisionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Record a human decision",
    description=(
        "Approve, reject, override, escalate, request evidence, confirm fraud or "
        "mark a false positive. The AI's verdict is preserved on the decision "
        "rather than overwritten and lost."
    ),
)
async def create_decision(
    claim_id: uuid.UUID,
    body: DecisionRequest,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
):
    # Per-action authorisation: the route is reachable by anyone signed in, but
    # the action decides which capability is actually needed.
    capability = ACTION_CAPABILITY.get(body.action, auth_service.DECIDE_CLAIMS)
    auth_service.require_capability(user.role, capability)

    claim = await claim_service.get_claim_detail(
        session, claim_id, organization_id=user.organization_id
    )

    decision = await decision_service.record_decision(
        session,
        claim=claim,
        actor=user,
        action=body.action,
        claim_item_id=body.claim_item_id,
        reason=body.reason,
        override_status=body.override_status,
    )

    await record_audit(
        session,
        actor=user,
        action=f"claim.decision.{body.action.value.lower()}",
        entity_type="claim",
        entity_id=str(claim_id),
        before={"ai_outcome": decision.previous_ai_outcome},
        after={
            "action": body.action.value,
            "claim_item_id": str(body.claim_item_id) if body.claim_item_id else None,
            "overrides_ai": decision.overrides_ai,
            "reason": decision.reason,
        },
        request=request,
    )

    # Reloaded so the author relationship is populated for the response.
    decisions = await decision_service.decisions_for_claim(session, claim_id)
    return _present_decision(next(d for d in decisions if d.id == decision.id))


@router.post(
    "/{claim_id}/close",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Close a claim",
)
async def close_claim(
    claim_id: uuid.UUID,
    body: CloseClaimRequest,
    request: Request,
    session: SessionDep,
    user: User = requires(auth_service.DECIDE_CLAIMS),
):
    claim = await claim_service.get_claim_detail(
        session, claim_id, organization_id=user.organization_id
    )
    previous = claim.status.value

    await decision_service.close_claim(
        session, claim=claim, actor=user, reason=body.reason
    )
    await record_audit(
        session,
        actor=user,
        action="claim.close",
        entity_type="claim",
        entity_id=str(claim_id),
        before={"status": previous},
        after={"status": "CLOSED", "reason": body.reason},
        request=request,
    )


@router.post(
    "/{claim_id}/investigations",
    response_model=InvestigationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Open an investigation",
)
async def open_investigation(
    claim_id: uuid.UUID,
    body: OpenInvestigationRequest,
    request: Request,
    session: SessionDep,
    user: User = requires(auth_service.INVESTIGATE),
):
    claim = await claim_service.get_claim_detail(
        session, claim_id, organization_id=user.organization_id
    )

    assignee = (
        await _assignee(session, user, body.assign_to_id) if body.assign_to_id else None
    )

    investigation = await investigation_service.open_investigation(
        session, claim=claim, actor=user, title=body.title, assign_to=assignee
    )

    await record_audit(
        session,
        actor=user,
        action="investigation.open",
        entity_type="investigation",
        entity_id=str(investigation.id),
        after={"claim_id": str(claim_id), "title": body.title},
        request=request,
    )

    return _present_investigation(
        await investigation_service.get_investigation(session, claim_id, investigation.id)
    )


@router.post(
    "/{claim_id}/investigations/{investigation_id}/assign",
    response_model=InvestigationOut,
    summary="Assign an investigation",
)
async def assign_investigation(
    claim_id: uuid.UUID,
    investigation_id: uuid.UUID,
    body: AssignRequest,
    request: Request,
    session: SessionDep,
    user: User = requires(auth_service.INVESTIGATE),
):
    claim = await claim_service.get_claim_detail(
        session, claim_id, organization_id=user.organization_id
    )
    investigation = await investigation_service.get_investigation(
        session, claim_id, investigation_id
    )
    assignee = await _assignee(session, user, body.assign_to_id)

    await investigation_service.assign(
        session, claim=claim, investigation=investigation, actor=user, assignee=assignee
    )
    await record_audit(
        session,
        actor=user,
        action="investigation.assign",
        entity_type="investigation",
        entity_id=str(investigation_id),
        # Every investigation-scoped entry carries the claim it belongs to, so a
        # claim's full history is one query against audit_logs rather than a
        # join back into the tables the log is meant to outlive.
        after={
            "claim_id": str(claim_id),
            "title": investigation.title,
            "assigned_to": str(assignee.id),
        },
        request=request,
    )

    return _present_investigation(
        await investigation_service.get_investigation(session, claim_id, investigation_id)
    )


@router.post(
    "/{claim_id}/investigations/{investigation_id}/notes",
    response_model=NoteOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a note to an investigation",
)
async def add_note(
    claim_id: uuid.UUID,
    investigation_id: uuid.UUID,
    body: NoteRequest,
    request: Request,
    session: SessionDep,
    user: User = requires(auth_service.INVESTIGATE),
):
    claim = await claim_service.get_claim_detail(
        session, claim_id, organization_id=user.organization_id
    )
    investigation = await investigation_service.get_investigation(
        session, claim_id, investigation_id
    )

    note = await investigation_service.add_note(
        session, claim=claim, investigation=investigation, actor=user, body=body.body
    )
    await record_audit(
        session,
        actor=user,
        action="investigation.note",
        entity_type="investigation",
        entity_id=str(investigation_id),
        after={
            "claim_id": str(claim_id),
            "title": investigation.title,
            "note_id": str(note.id),
            "body": note.body,
        },
        request=request,
    )

    return NoteOut(
        id=note.id,
        body=note.body,
        author=user.full_name or user.email,
        created_at=note.created_at,
    )


@router.post(
    "/{claim_id}/investigations/{investigation_id}/resolve",
    response_model=InvestigationOut,
    summary="Resolve an investigation",
)
async def resolve_investigation(
    claim_id: uuid.UUID,
    investigation_id: uuid.UUID,
    body: ResolveRequest,
    request: Request,
    session: SessionDep,
    user: User = requires(auth_service.INVESTIGATE),
):
    claim = await claim_service.get_claim_detail(
        session, claim_id, organization_id=user.organization_id
    )
    investigation = await investigation_service.get_investigation(
        session, claim_id, investigation_id
    )

    await investigation_service.resolve(
        session, claim=claim, investigation=investigation, actor=user,
        resolution=body.resolution,
    )
    await record_audit(
        session,
        actor=user,
        action="investigation.resolve",
        entity_type="investigation",
        entity_id=str(investigation_id),
        after={
            "claim_id": str(claim_id),
            "title": investigation.title,
            "resolution": body.resolution,
        },
        request=request,
    )

    return _present_investigation(
        await investigation_service.get_investigation(session, claim_id, investigation_id)
    )
