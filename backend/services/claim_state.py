"""The claim state machine.

The prototype moved claims between statuses by assigning to `claim.status`
wherever it felt necessary, and coordinated concurrent jobs by polling. The
audit task slept in a 60×2s loop waiting for extraction to finish. That is a
race condition with a timeout bolted on: it wastes two minutes on the happy
path's worst case, silently gives up on the slow one, and encodes the ordering
rules nowhere.

Transitions are declared here instead. A move that is not in the table is a bug
and raises rather than quietly corrupting the claim's history, and every accepted
move writes a timeline event, which is what finally makes `events` a real table
rather than an empty one.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from models import Claim, ClaimStatus, Event, EventKind

logger = logging.getLogger(__name__)

# Terminal states: nothing proceeds from here without human action.
TERMINAL = {ClaimStatus.CLOSED, ClaimStatus.FAILED, ClaimStatus.LLM_UNAVAILABLE}

# What may follow what. Re-entry into the same state is handled separately as a
# no-op so that a retried job does not have to know whether it already ran.
ALLOWED: dict[ClaimStatus, set[ClaimStatus]] = {
    ClaimStatus.RECEIVED: {
        ClaimStatus.EXTRACTING, ClaimStatus.FAILED, ClaimStatus.LLM_UNAVAILABLE,
    },
    ClaimStatus.EXTRACTING: {
        ClaimStatus.EXTRACTED, ClaimStatus.FAILED, ClaimStatus.LLM_UNAVAILABLE,
    },
    ClaimStatus.EXTRACTED: {
        ClaimStatus.AUDITING, ClaimStatus.FAILED, ClaimStatus.LLM_UNAVAILABLE,
        # Re-extraction of a corrected document is legitimate.
        ClaimStatus.EXTRACTING,
    },
    ClaimStatus.AUDITING: {
        ClaimStatus.AUDIT_COMPLETE, ClaimStatus.FAILED, ClaimStatus.LLM_UNAVAILABLE,
    },
    ClaimStatus.AUDIT_COMPLETE: {
        ClaimStatus.APPEAL_GENERATED, ClaimStatus.NO_APPEAL_NEEDED,
        ClaimStatus.CLOSED, ClaimStatus.FAILED, ClaimStatus.LLM_UNAVAILABLE,
        # Re-auditing against a different policy is a normal analyst action.
        ClaimStatus.AUDITING,
    },
    ClaimStatus.APPEAL_GENERATED: {ClaimStatus.CLOSED, ClaimStatus.AUDITING},
    ClaimStatus.NO_APPEAL_NEEDED: {ClaimStatus.CLOSED, ClaimStatus.AUDITING},
    ClaimStatus.CLOSED: set(),
    # Recoverable failures: fixing the cause and re-running is the whole point.
    ClaimStatus.FAILED: {ClaimStatus.EXTRACTING, ClaimStatus.AUDITING},
    ClaimStatus.LLM_UNAVAILABLE: {ClaimStatus.EXTRACTING, ClaimStatus.AUDITING},
}

EVENT_KIND = {
    ClaimStatus.EXTRACTING: EventKind.SYSTEM,
    ClaimStatus.EXTRACTED: EventKind.EVIDENCE,
    ClaimStatus.AUDITING: EventKind.SYSTEM,
    ClaimStatus.AUDIT_COMPLETE: EventKind.AI_FINDING,
    ClaimStatus.APPEAL_GENERATED: EventKind.AI_FINDING,
    ClaimStatus.NO_APPEAL_NEEDED: EventKind.AI_FINDING,
}

DESCRIPTION = {
    ClaimStatus.RECEIVED: "Claim opened",
    ClaimStatus.EXTRACTING: "Reading the bill",
    ClaimStatus.EXTRACTED: "Line items extracted",
    ClaimStatus.AUDITING: "Adjudicating against the policy",
    ClaimStatus.AUDIT_COMPLETE: "Adjudication complete",
    ClaimStatus.APPEAL_GENERATED: "Appeal letter drafted",
    ClaimStatus.NO_APPEAL_NEEDED: "No appeal needed",
    ClaimStatus.CLOSED: "Claim closed",
    ClaimStatus.FAILED: "Processing failed",
    ClaimStatus.LLM_UNAVAILABLE: "AI reasoning unavailable",
}


class InvalidTransition(Exception):
    """An attempt to move a claim somewhere it cannot go from where it is."""

    def __init__(self, current: ClaimStatus, target: ClaimStatus):
        super().__init__(
            f"A claim cannot move from {current.value} to {target.value}."
        )
        self.current = current
        self.target = target


def can_transition(current: ClaimStatus, target: ClaimStatus) -> bool:
    if current == target:
        return True  # idempotent re-entry
    return target in ALLOWED.get(current, set())


async def transition(
    session: AsyncSession,
    claim: Claim,
    target: ClaimStatus,
    *,
    summary: str | None = None,
    detail: str | None = None,
    actor_id=None,
    payload: dict | None = None,
) -> bool:
    """Move a claim to `target`, recording the move on its timeline.

    Returns False when the claim is already in the target state; a retried job
    is not an error. Raises InvalidTransition for a move the table forbids.
    """
    current = claim.status

    if current == target:
        logger.debug("Claim %s already %s; no transition.", claim.id, target.value)
        return False

    if not can_transition(current, target):
        raise InvalidTransition(current, target)

    claim.status = target

    session.add(
        Event(
            claim_id=claim.id,
            actor_id=actor_id,
            kind=EVENT_KIND.get(target, EventKind.STATUS_CHANGE),
            summary=summary or DESCRIPTION.get(target, f"Status: {target.value}"),
            detail=detail,
            payload={"from": current.value, "to": target.value, **(payload or {})},
        )
    )

    logger.info("Claim %s: %s -> %s", claim.id, current.value, target.value)
    return True


async def record(
    session: AsyncSession,
    claim: Claim,
    *,
    kind: EventKind,
    summary: str,
    detail: str | None = None,
    actor_id=None,
    payload: dict | None = None,
) -> None:
    """Add a timeline event that is not a status change.

    Evidence arriving, a risk score being computed, a human leaving a note: all
    belong on the same ordered stream as the status moves, so that "what happened
    to this claim" is one query.
    """
    session.add(
        Event(
            claim_id=claim.id,
            actor_id=actor_id,
            kind=kind,
            summary=summary,
            detail=detail,
            payload=payload,
        )
    )
