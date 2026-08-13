"""Human decisions on a claim.

The point of this module is that a person's decision is recorded *alongside* what
the AI had said, not on top of it. The model's verdict is never edited or
deleted; an override adds a row saying a named person disagreed, and why.

Three things fall out of that:

  * an analyst can always see what they are disagreeing with
  * the audit trail shows who decided what and when
  * P11's feedback dataset is a query, not an archaeology project

Which actions a role may take is enforced at the route; this module records what
was decided and keeps the claim's derived state consistent with it.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.errors import ConflictError, NotFoundError, ValidationError
from models import (
    AdjudicationStatus,
    Claim,
    ClaimItem,
    ClaimStatus,
    DecisionAction,
    EventKind,
    HumanDecision,
    User,
)
from services import claim_state

# Actions that settle a line item, and the verdict each one lands on. An action
# not in this table is a workflow step rather than an adjudication.
ITEM_OUTCOME = {
    DecisionAction.APPROVE: AdjudicationStatus.APPROVED,
    DecisionAction.REJECT: AdjudicationStatus.REJECTED,
    DecisionAction.MARK_FALSE_POSITIVE: AdjudicationStatus.APPROVED,
    DecisionAction.CONFIRM_FRAUD: AdjudicationStatus.REJECTED,
}

# Actions that must name a specific line item, because they change its verdict.
ITEM_SCOPED = set(ITEM_OUTCOME) | {DecisionAction.OVERRIDE}

# Actions where a written reason is required rather than merely welcome.
# Disagreeing with the model, or alleging fraud, has to be explainable later.
REASON_REQUIRED = {
    DecisionAction.OVERRIDE,
    DecisionAction.REJECT,
    DecisionAction.CONFIRM_FRAUD,
    DecisionAction.MARK_FALSE_POSITIVE,
    DecisionAction.ESCALATE,
}


async def _load_item(session: AsyncSession, claim_id: uuid.UUID, item_id: uuid.UUID) -> ClaimItem:
    item = (
        await session.execute(
            select(ClaimItem)
            .options(selectinload(ClaimItem.audit_finding))
            .where(ClaimItem.id == item_id, ClaimItem.claim_id == claim_id)
        )
    ).scalars().first()

    if item is None:
        raise NotFoundError(f"No line item {item_id} on this claim.")
    return item


async def record_decision(
    session: AsyncSession,
    *,
    claim: Claim,
    actor: User,
    action: DecisionAction,
    claim_item_id: uuid.UUID | None = None,
    reason: str = "",
    override_status: AdjudicationStatus | None = None,
) -> HumanDecision:
    """Record a decision and apply whatever it changes.

    Returns the persisted HumanDecision. Raises rather than silently ignoring a
    request that does not make sense, such as deciding on a claim that was never
    adjudicated, or overriding without saying why.
    """
    reason = (reason or "").strip()

    if action in REASON_REQUIRED and not reason:
        raise ValidationError(
            f"A reason is required when the action is {action.value.lower().replace('_', ' ')}."
        )

    if action in ITEM_SCOPED and claim_item_id is None:
        raise ValidationError(
            f"{action.value} applies to a specific line item; none was given."
        )

    if claim.status in (ClaimStatus.RECEIVED, ClaimStatus.EXTRACTING, ClaimStatus.EXTRACTING):
        raise ConflictError(
            "This claim has not been adjudicated yet, so there is nothing to decide on."
        )

    item = None
    previous_outcome = None

    if claim_item_id is not None:
        item = await _load_item(session, claim.id, claim_item_id)
        finding = item.audit_finding
        previous_outcome = finding.status.value if finding else None

        target = override_status or ITEM_OUTCOME.get(action)
        if action is DecisionAction.OVERRIDE and target is None:
            raise ValidationError(
                "An override must state the verdict it is replacing the AI's with."
            )

        if target is not None:
            if finding is None:
                raise ConflictError(
                    "This line item has no AI verdict yet, so there is nothing to override."
                )
            # The AI's verdict is replaced on the finding (the claim has one
            # current answer per line) but the previous value is preserved on
            # the decision row below, so nothing is lost.
            finding.status = target
            item.allowed_amount = (
                item.billed_amount if target is AdjudicationStatus.APPROVED else None
            )

    overrides = bool(
        previous_outcome
        and (override_status or ITEM_OUTCOME.get(action))
        and previous_outcome != (override_status or ITEM_OUTCOME.get(action)).value
    )

    decision = HumanDecision(
        claim_id=claim.id,
        claim_item_id=claim_item_id,
        decided_by_id=actor.id,
        action=action,
        reason=reason,
        previous_ai_outcome=previous_outcome,
        overrides_ai=overrides,
    )
    session.add(decision)

    await claim_state.record(
        session,
        claim,
        kind=EventKind.HUMAN_ACTION,
        summary=_summarise(action, actor, item),
        detail=reason or None,
        actor_id=actor.id,
        payload={
            "action": action.value,
            "claim_item_id": str(claim_item_id) if claim_item_id else None,
            "previous_ai_outcome": previous_outcome,
            "overrides_ai": overrides,
        },
    )

    await session.flush()
    return decision


def _summarise(action: DecisionAction, actor: User, item: ClaimItem | None) -> str:
    verb = {
        DecisionAction.APPROVE: "approved",
        DecisionAction.REJECT: "rejected",
        DecisionAction.ESCALATE: "escalated",
        DecisionAction.REQUEST_EVIDENCE: "requested further evidence for",
        DecisionAction.OVERRIDE: "overrode the AI verdict on",
        DecisionAction.MARK_FALSE_POSITIVE: "marked a false positive on",
        DecisionAction.CONFIRM_FRAUD: "confirmed fraud on",
    }.get(action, action.value.lower())

    subject = f"'{item.description}'" if item is not None else "this claim"
    return f"{actor.full_name or actor.email} {verb} {subject}"


async def decisions_for_claim(
    session: AsyncSession, claim_id: uuid.UUID
) -> list[HumanDecision]:
    return list(
        (
            await session.execute(
                select(HumanDecision)
                .options(selectinload(HumanDecision.decided_by))
                .where(HumanDecision.claim_id == claim_id)
                .order_by(HumanDecision.created_at)
            )
        )
        .scalars()
        .all()
    )


async def close_claim(
    session: AsyncSession, *, claim: Claim, actor: User, reason: str
) -> None:
    """Mark a claim finished. The state machine rejects it if that is not valid."""
    await claim_state.transition(
        session,
        claim,
        ClaimStatus.CLOSED,
        summary=f"Closed by {actor.full_name or actor.email}",
        detail=reason or None,
        actor_id=actor.id,
    )
