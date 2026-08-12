"""Orchestration: state transitions, idempotency and the timeline.

The guarantee being tested is that running any stage twice is safe. The
prototype could not make that claim — a re-audit inserted a second verdict per
line, and the ORM then returned whichever it happened to load first.
"""

import uuid

import pytest

from models import AdjudicationStatus, AuditFinding, Claim, ClaimItem, ClaimStatus, Event
from services import claim_state
from services.claim_state import InvalidTransition


# --- the transition table --------------------------------------------------

def test_the_happy_path_is_permitted():
    order = [
        ClaimStatus.RECEIVED, ClaimStatus.EXTRACTING, ClaimStatus.EXTRACTED,
        ClaimStatus.AUDITING, ClaimStatus.AUDIT_COMPLETE,
        ClaimStatus.APPEAL_GENERATED, ClaimStatus.CLOSED,
    ]
    for current, target in zip(order, order[1:]):
        assert claim_state.can_transition(current, target), f"{current} -> {target}"


def test_stages_cannot_be_skipped():
    """A claim must not appear adjudicated without having been extracted."""
    assert not claim_state.can_transition(ClaimStatus.RECEIVED, ClaimStatus.AUDIT_COMPLETE)
    assert not claim_state.can_transition(ClaimStatus.RECEIVED, ClaimStatus.AUDITING)
    assert not claim_state.can_transition(ClaimStatus.EXTRACTING, ClaimStatus.AUDIT_COMPLETE)


def test_a_closed_claim_is_final():
    for target in ClaimStatus:
        if target is ClaimStatus.CLOSED:
            continue
        assert not claim_state.can_transition(ClaimStatus.CLOSED, target)


def test_failures_are_recoverable():
    """Fixing the cause and re-running is the entire point of a failed state."""
    for failed in (ClaimStatus.FAILED, ClaimStatus.LLM_UNAVAILABLE):
        assert claim_state.can_transition(failed, ClaimStatus.EXTRACTING)
        assert claim_state.can_transition(failed, ClaimStatus.AUDITING)


def test_re_auditing_a_completed_claim_is_allowed():
    """Re-running against a corrected policy is a normal analyst action."""
    assert claim_state.can_transition(ClaimStatus.AUDIT_COMPLETE, ClaimStatus.AUDITING)


def test_every_status_appears_in_the_table():
    """A status with no entry would silently permit nothing."""
    for status in ClaimStatus:
        assert status in claim_state.ALLOWED, status


def test_re_entry_is_permitted_so_retries_are_safe():
    for status in ClaimStatus:
        assert claim_state.can_transition(status, status)


# --- transitions in the database -------------------------------------------

@pytest.fixture
async def fresh_claim(session):
    from core.bootstrap import ensure_demo_tenant
    from core.bootstrap import new_claim_reference

    org, user = await ensure_demo_tenant(session)
    claim = Claim(
        organization_id=org.id,
        created_by_id=user.id if user else None,
        reference=new_claim_reference(),
        status=ClaimStatus.RECEIVED,
    )
    session.add(claim)
    await session.commit()
    await session.refresh(claim)

    yield claim

    await session.delete(claim)
    await session.commit()


async def test_a_transition_writes_a_timeline_event(session, fresh_claim):
    from sqlalchemy import select

    moved = await claim_state.transition(session, fresh_claim, ClaimStatus.EXTRACTING)
    await session.commit()

    assert moved is True
    assert fresh_claim.status is ClaimStatus.EXTRACTING

    events = (
        await session.execute(select(Event).where(Event.claim_id == fresh_claim.id))
    ).scalars().all()

    assert len(events) == 1
    assert events[0].payload["from"] == "RECEIVED"
    assert events[0].payload["to"] == "EXTRACTING"


async def test_repeating_a_transition_is_a_no_op(session, fresh_claim):
    from sqlalchemy import func, select

    await claim_state.transition(session, fresh_claim, ClaimStatus.EXTRACTING)
    await session.commit()

    again = await claim_state.transition(session, fresh_claim, ClaimStatus.EXTRACTING)
    await session.commit()

    assert again is False, "a repeated transition must not be treated as a move"

    count = await session.scalar(
        select(func.count()).select_from(Event).where(Event.claim_id == fresh_claim.id)
    )
    assert count == 1, "a no-op must not add a second event"


async def test_an_illegal_transition_raises(session, fresh_claim):
    with pytest.raises(InvalidTransition):
        await claim_state.transition(session, fresh_claim, ClaimStatus.AUDIT_COMPLETE)

    assert fresh_claim.status is ClaimStatus.RECEIVED, "a rejected move must not apply"


async def test_a_non_status_event_can_be_recorded(session, fresh_claim):
    from sqlalchemy import select

    from models import EventKind

    await claim_state.record(
        session, fresh_claim, kind=EventKind.HUMAN_ACTION, summary="Assigned to review"
    )
    await session.commit()

    events = (
        await session.execute(select(Event).where(Event.claim_id == fresh_claim.id))
    ).scalars().all()
    assert [e.summary for e in events] == ["Assigned to review"]
    assert fresh_claim.status is ClaimStatus.RECEIVED


# --- idempotency at the database level -------------------------------------

async def test_a_line_item_cannot_hold_two_verdicts(session, fresh_claim):
    """The constraint that makes re-auditing safe.

    Without it a second audit inserted another finding per line and the claim
    held two contradictory verdicts.
    """
    from sqlalchemy.exc import IntegrityError

    item = ClaimItem(
        claim_id=fresh_claim.id, category="Room Rent",
        description="Shared room", billed_amount=1000.0,
    )
    session.add(item)
    await session.commit()

    session.add(
        AuditFinding(
            claim_item_id=item.id, status=AdjudicationStatus.APPROVED, reason="first"
        )
    )
    await session.commit()

    session.add(
        AuditFinding(
            claim_item_id=item.id, status=AdjudicationStatus.REJECTED, reason="second"
        )
    )
    with pytest.raises(IntegrityError):
        await session.commit()

    await session.rollback()


# --- the audit task's prerequisite handling --------------------------------

class NoopQueue:
    def __init__(self):
        self.calls = []

    async def enqueue_job(self, name, *args):
        self.calls.append((name, *args))
        return None


async def test_audit_defers_while_extraction_is_running(
    session, fresh_claim, sample_policy
):
    """No polling: the task stands down and records which policy to use."""
    from tasks.audit_claim import audit_claim_task

    policy_id = str(sample_policy.id)
    result = await audit_claim_task(
        {"job_id": "t", "redis": NoopQueue()}, str(fresh_claim.id), policy_id
    )

    assert result["status"] == "deferred"
    assert result["reason"] == "extraction_in_progress"

    await session.refresh(fresh_claim)
    assert str(fresh_claim.policy_id) == policy_id, (
        "the deferred audit must record which policy to use when it resumes"
    )


async def test_audit_refuses_a_failed_claim(session, fresh_claim):
    fresh_claim.status = ClaimStatus.FAILED
    await session.commit()

    from tasks.audit_claim import audit_claim_task

    result = await audit_claim_task(
        {"job_id": "t", "redis": NoopQueue()}, str(fresh_claim.id), str(uuid.uuid4())
    )
    assert result["status"] == "error"
    assert result["reason"] == "claim_failed"


async def test_audit_of_an_unknown_claim_is_an_error_not_a_crash():
    from tasks.audit_claim import audit_claim_task

    result = await audit_claim_task(
        {"job_id": "t", "redis": NoopQueue()}, str(uuid.uuid4()), str(uuid.uuid4())
    )
    assert result["status"] == "error"
