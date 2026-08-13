"""Human decisions, investigations, and the audit trail.

The guarantee under test is that a person's decision never destroys the AI's:
an override records what it overrode. And that every action reaches the
append-only audit log, so the claim's history survives independently of the
tables it describes.
"""

import uuid

import pytest
from sqlalchemy import select

from models import (
    AdjudicationStatus,
    AuditFinding,
    AuditLog,
    Claim,
    ClaimItem,
    ClaimStatus,
    DecisionAction,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def audited_claim(session):
    """A claim with one adjudicated line, ready to be decided on."""
    from core.bootstrap import ensure_demo_tenant, new_claim_reference

    org, user = await ensure_demo_tenant(session)
    claim = Claim(
        organization_id=org.id,
        created_by_id=user.id if user else None,
        reference=new_claim_reference(),
        status=ClaimStatus.AUDIT_COMPLETE,
        total_billed=13500.0,
    )
    session.add(claim)
    await session.flush()

    item = ClaimItem(
        claim_id=claim.id, line_number=1, category="Room Rent",
        description="Shared room, 3 days", billed_amount=13500.0,
    )
    session.add(item)
    await session.flush()

    session.add(
        AuditFinding(
            claim_item_id=item.id,
            status=AdjudicationStatus.REJECTED,
            reason="Exceeds the room rent limit.",
            confidence=0.8,
        )
    )
    await session.commit()
    await session.refresh(claim)
    await session.refresh(item)

    yield claim, item

    await session.delete(claim)
    await session.commit()


# --- authorisation per action ----------------------------------------------

async def test_analyst_cannot_approve(client, as_analyst, audited_claim):
    """Settling a line item is a senior authority."""
    claim, item = audited_claim
    res = await client.post(
        f"/api/v1/claims/{claim.id}/decisions",
        json={"action": "APPROVE", "claim_item_id": str(item.id)},
        headers=as_analyst,
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "forbidden"


async def test_analyst_can_escalate(client, as_analyst, audited_claim):
    """Raising a concern is not the same authority as settling one."""
    claim, _ = audited_claim
    res = await client.post(
        f"/api/v1/claims/{claim.id}/decisions",
        json={"action": "ESCALATE", "reason": "Room rate looks unusual for this city."},
        headers=as_analyst,
    )
    assert res.status_code == 201


async def test_senior_can_approve(client, as_senior, audited_claim):
    claim, item = audited_claim
    res = await client.post(
        f"/api/v1/claims/{claim.id}/decisions",
        json={"action": "APPROVE", "claim_item_id": str(item.id)},
        headers=as_senior,
    )
    assert res.status_code == 201


async def test_auditor_can_read_but_not_decide(client, as_auditor, audited_claim):
    claim, item = audited_claim

    assert (await client.get(f"/api/v1/claims/{claim.id}/review", headers=as_auditor)).status_code == 200

    denied = await client.post(
        f"/api/v1/claims/{claim.id}/decisions",
        json={"action": "APPROVE", "claim_item_id": str(item.id)},
        headers=as_auditor,
    )
    assert denied.status_code == 403


async def test_auditor_cannot_open_an_investigation(client, as_auditor, audited_claim):
    claim, _ = audited_claim
    res = await client.post(
        f"/api/v1/claims/{claim.id}/investigations",
        json={"title": "Check the room category"},
        headers=as_auditor,
    )
    assert res.status_code == 403


async def test_anonymous_cannot_decide(client, audited_claim):
    claim, item = audited_claim
    res = await client.post(
        f"/api/v1/claims/{claim.id}/decisions",
        json={"action": "APPROVE", "claim_item_id": str(item.id)},
    )
    assert res.status_code == 401


# --- the override contract -------------------------------------------------

async def test_an_override_records_what_it_overrode(client, as_senior, audited_claim, session):
    """The AI's verdict must survive being disagreed with."""
    claim, item = audited_claim

    res = await client.post(
        f"/api/v1/claims/{claim.id}/decisions",
        json={
            "action": "OVERRIDE",
            "claim_item_id": str(item.id),
            "override_status": "APPROVED",
            "reason": "The hospital confirmed the shared-room rate in writing.",
        },
        headers=as_senior,
    )
    assert res.status_code == 201

    body = res.json()
    assert body["previous_ai_outcome"] == "REJECTED", "the AI's verdict must be preserved"
    assert body["overrides_ai"] is True
    assert body["decided_by"]

    # And the line item now carries the human's verdict.
    await session.refresh(item)
    finding = (
        await session.execute(
            select(AuditFinding).where(AuditFinding.claim_item_id == item.id)
        )
    ).scalars().first()
    assert finding.status is AdjudicationStatus.APPROVED


async def test_agreeing_with_the_ai_is_not_an_override(client, as_senior, audited_claim):
    """Confirming the model is a decision, but not a disagreement."""
    claim, item = audited_claim
    res = await client.post(
        f"/api/v1/claims/{claim.id}/decisions",
        json={"action": "REJECT", "claim_item_id": str(item.id),
              "reason": "Agreed, the rate exceeds the cap."},
        headers=as_senior,
    )
    assert res.json()["overrides_ai"] is False


async def test_override_requires_a_reason(client, as_senior, audited_claim):
    claim, item = audited_claim
    res = await client.post(
        f"/api/v1/claims/{claim.id}/decisions",
        json={"action": "OVERRIDE", "claim_item_id": str(item.id),
              "override_status": "APPROVED"},
        headers=as_senior,
    )
    assert res.status_code == 422
    assert "reason" in res.json()["error"]["message"].lower()


async def test_override_requires_a_target_verdict(client, as_senior, audited_claim):
    claim, item = audited_claim
    res = await client.post(
        f"/api/v1/claims/{claim.id}/decisions",
        json={"action": "OVERRIDE", "claim_item_id": str(item.id), "reason": "Because."},
        headers=as_senior,
    )
    assert res.status_code == 422


async def test_item_scoped_action_requires_an_item(client, as_senior, audited_claim):
    claim, _ = audited_claim
    res = await client.post(
        f"/api/v1/claims/{claim.id}/decisions",
        json={"action": "APPROVE"},
        headers=as_senior,
    )
    assert res.status_code == 422


async def test_cannot_decide_on_an_unadjudicated_claim(client, as_senior, session):
    from core.bootstrap import ensure_demo_tenant, new_claim_reference

    org, user = await ensure_demo_tenant(session)
    claim = Claim(
        organization_id=org.id, created_by_id=user.id if user else None,
        reference=new_claim_reference(), status=ClaimStatus.RECEIVED,
    )
    session.add(claim)
    await session.commit()

    try:
        res = await client.post(
            f"/api/v1/claims/{claim.id}/decisions",
            json={"action": "ESCALATE", "reason": "Looks odd."},
            headers=as_senior,
        )
        assert res.status_code == 409
    finally:
        await session.delete(claim)
        await session.commit()


# --- investigations --------------------------------------------------------

async def test_investigation_lifecycle(client, as_senior, audited_claim):
    claim, _ = audited_claim

    opened = await client.post(
        f"/api/v1/claims/{claim.id}/investigations",
        json={"title": "Confirm the room category with the hospital"},
        headers=as_senior,
    )
    assert opened.status_code == 201
    investigation_id = opened.json()["id"]
    assert opened.json()["status"] == "OPEN"

    noted = await client.post(
        f"/api/v1/claims/{claim.id}/investigations/{investigation_id}/notes",
        json={"body": "Called the billing desk; awaiting a written rate card."},
        headers=as_senior,
    )
    assert noted.status_code == 201

    resolved = await client.post(
        f"/api/v1/claims/{claim.id}/investigations/{investigation_id}/resolve",
        json={"resolution": "Rate card received; the shared-room rate is confirmed."},
        headers=as_senior,
    )
    assert resolved.status_code == 200
    body = resolved.json()
    assert body["status"] == "RESOLVED"
    assert body["closed_at"]
    assert len(body["notes"]) == 1


async def test_resolving_twice_is_a_conflict(client, as_senior, audited_claim):
    claim, _ = audited_claim
    opened = await client.post(
        f"/api/v1/claims/{claim.id}/investigations",
        json={"title": "Something to close"},
        headers=as_senior,
    )
    investigation_id = opened.json()["id"]

    payload = {"resolution": "Done."}
    first = await client.post(
        f"/api/v1/claims/{claim.id}/investigations/{investigation_id}/resolve",
        json=payload, headers=as_senior,
    )
    second = await client.post(
        f"/api/v1/claims/{claim.id}/investigations/{investigation_id}/resolve",
        json=payload, headers=as_senior,
    )
    assert first.status_code == 200
    assert second.status_code == 409


async def test_an_auditor_cannot_be_assigned_work(client, as_senior, audited_claim, session):
    """Assigning to a read-only role would create an unactionable item."""
    from core.bootstrap import ensure_demo_tenant
    from models import User, UserRole

    org, _ = await ensure_demo_tenant(session)
    auditor = (
        await session.execute(
            select(User).where(User.organization_id == org.id, User.role == UserRole.AUDITOR)
        )
    ).scalars().first()

    claim, _ = audited_claim
    opened = await client.post(
        f"/api/v1/claims/{claim.id}/investigations",
        json={"title": "Needs an owner"}, headers=as_senior,
    )
    investigation_id = opened.json()["id"]

    res = await client.post(
        f"/api/v1/claims/{claim.id}/investigations/{investigation_id}/assign",
        json={"assign_to_id": str(auditor.id)}, headers=as_senior,
    )
    assert res.status_code == 409


async def test_cannot_assign_someone_from_another_organization(
    client, as_senior, audited_claim, session, foreign_org
):
    from models import User, UserRole

    outsider = User(
        organization_id=foreign_org.id, email=f"outsider-{uuid.uuid4().hex[:6]}@rival.test",
        full_name="Outsider", role=UserRole.ANALYST,
    )
    session.add(outsider)
    await session.commit()

    claim, _ = audited_claim
    opened = await client.post(
        f"/api/v1/claims/{claim.id}/investigations",
        json={"title": "Ownership check"}, headers=as_senior,
    )
    investigation_id = opened.json()["id"]

    try:
        res = await client.post(
            f"/api/v1/claims/{claim.id}/investigations/{investigation_id}/assign",
            json={"assign_to_id": str(outsider.id)}, headers=as_senior,
        )
        assert res.status_code == 404
    finally:
        await session.delete(outsider)
        await session.commit()


# --- the gate: history reconstructs from audit_logs alone ------------------

async def test_every_action_reaches_the_append_only_audit_log(
    client, as_senior, audited_claim, session
):
    """The P8 gate.

    After a sequence of actions, audit_logs must contain enough to reconstruct
    what happened without consulting the tables it describes.
    """
    claim, item = audited_claim

    before = await session.scalar(
        select(AuditLog.id).where(AuditLog.entity_id == str(claim.id)).limit(1)
    )
    assert before is None, "fixture claim should start with no audit entries"

    await client.post(
        f"/api/v1/claims/{claim.id}/decisions",
        json={"action": "ESCALATE", "reason": "Rate looks high."},
        headers=as_senior,
    )
    await client.post(
        f"/api/v1/claims/{claim.id}/decisions",
        json={"action": "OVERRIDE", "claim_item_id": str(item.id),
              "override_status": "APPROVED", "reason": "Rate card confirms it."},
        headers=as_senior,
    )
    opened = await client.post(
        f"/api/v1/claims/{claim.id}/investigations",
        json={"title": "Confirm with the insurer"}, headers=as_senior,
    )
    await client.post(
        f"/api/v1/claims/{claim.id}/investigations/{opened.json()['id']}/notes",
        json={"body": "Spoke to the insurer."}, headers=as_senior,
    )
    await client.post(f"/api/v1/claims/{claim.id}/close",
                      json={"reason": "Settled."}, headers=as_senior)

    # Queried by claim alone, with no join back into the tables the log describes.
    # That is the guarantee: the trail stands on its own.
    from sqlalchemy import or_

    entries = (
        await session.execute(
            select(AuditLog)
            .where(
                or_(
                    AuditLog.entity_id == str(claim.id),
                    AuditLog.after["claim_id"].astext == str(claim.id),
                )
            )
            .order_by(AuditLog.created_at)
        )
    ).scalars().all()

    actions = [e.action for e in entries]
    assert "claim.decision.escalate" in actions
    assert "claim.decision.override" in actions
    assert "investigation.open" in actions
    assert "investigation.note" in actions, (
        "an investigation note must be reachable from the claim it belongs to"
    )
    assert "claim.close" in actions

    # Each entry must identify who, and carry enough context to be meaningful.
    for entry in entries:
        assert entry.actor_id is not None, f"{entry.action} has no actor"
        assert entry.request_id, f"{entry.action} has no request id"

    override = next(e for e in entries if e.action == "claim.decision.override")
    assert override.before["ai_outcome"] == "REJECTED"
    assert override.after["overrides_ai"] is True
    assert override.after["reason"]


async def test_audit_entries_cannot_be_altered(session, audited_claim):
    """The trail is append-only in the database, not merely by convention."""
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    claim, _ = audited_claim
    session.add(
        AuditLog(action="test.entry", entity_type="claim", entity_id=str(claim.id))
    )
    await session.commit()

    with pytest.raises(DBAPIError):
        await session.execute(
            text("UPDATE audit_logs SET action = 'tampered' WHERE action = 'test.entry'")
        )
        await session.commit()
    await session.rollback()
