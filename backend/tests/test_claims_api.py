import uuid

import pytest

from tests.conftest import MINIMAL_PDF

pytestmark = pytest.mark.asyncio


async def test_list_returns_a_page_envelope(client, as_analyst):
    res = await client.get("/api/v1/claims", headers=as_analyst)
    assert res.status_code == 200

    body = res.json()
    assert set(body) == {"items", "next_cursor", "has_more"}
    assert isinstance(body["items"], list)


async def test_list_items_carry_the_summary_contract(client, as_analyst, sample_claim):
    body = (await client.get("/api/v1/claims", headers=as_analyst)).json()
    item = next(i for i in body["items"] if i["reference"] == sample_claim.reference)

    assert set(item) == {
        "id", "reference", "status", "total_billed",
        "total_approved", "currency", "created_at",
    }


async def test_pagination_advances_without_repeating(client, as_analyst, sample_claim):
    """A cursor must not return a row the previous page already returned."""
    first = (await client.get("/api/v1/claims?limit=1", headers=as_analyst)).json()
    assert len(first["items"]) <= 1

    if not first["has_more"]:
        pytest.skip("needs more than one claim to exercise paging")

    second = (await client.get(f"/api/v1/claims?limit=1&cursor={first['next_cursor']}", headers=as_analyst)).json()
    assert first["items"][0]["id"] != second["items"][0]["id"]


async def test_detail_includes_items_and_risk_keys(client, as_analyst, sample_claim):
    res = await client.get(f"/api/v1/claims/{sample_claim.id}", headers=as_analyst)
    assert res.status_code == 200

    body = res.json()
    assert body["reference"] == sample_claim.reference
    for key in ("items", "risk", "signals", "claimant_name", "provider_name"):
        assert key in body


async def test_upload_queues_extraction(client, as_analyst, queue, session):
    res = await client.post(
        "/api/v1/claims",
        files={"file": ("bill.pdf", MINIMAL_PDF, "application/pdf")},
        headers=as_analyst,
    )
    assert res.status_code == 202

    body = res.json()
    assert body["reference"].startswith("CLM-")
    assert body["job_id"]

    try:
        # The contract is that extraction was queued for this claim's document.
        name, claim_id, document_id = queue.calls[-1]
        assert name == "extract_bill_task"
        assert claim_id == body["claim_id"]
        assert document_id == body["document_id"]
    finally:
        # This endpoint really writes a claim, so the test has to remove it.
        # Left behind, uploads accumulate and pollute the demo data.
        from models import Claim

        claim = await session.get(Claim, uuid.UUID(body["claim_id"]))
        if claim:
            await session.delete(claim)
            await session.commit()


async def test_upload_rejects_a_non_pdf_masquerading_as_one(client, as_analyst, queue):
    """The prototype accepted this and crashed the worker's PDF parser."""
    before = len(queue.calls)
    res = await client.post(
        "/api/v1/claims",
        files={"file": ("bill.pdf", b"this is plain text, not a PDF", "application/pdf")},
        headers=as_analyst,
    )

    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_failed"
    assert len(queue.calls) == before, "nothing should be queued for an invalid upload"


async def test_upload_rejects_empty_file(client, as_analyst):
    res = await client.post(
        "/api/v1/claims",
        files={"file": ("bill.pdf", b"", "application/pdf")},
        headers=as_analyst,
    )
    assert res.status_code == 422


async def test_audit_requires_an_existing_policy(client, as_analyst, sample_claim, queue):
    before = len(queue.calls)
    res = await client.post(
        f"/api/v1/claims/{sample_claim.id}/audit",
        json={"policy_id": str(uuid.uuid4())},
        headers=as_analyst,
    )

    assert res.status_code == 404
    assert len(queue.calls) == before, "an unauditable claim must not be queued"


async def test_audit_queues_with_both_ids(client, as_analyst, sample_claim, sample_policy, queue):
    res = await client.post(
        f"/api/v1/claims/{sample_claim.id}/audit",
        json={"policy_id": str(sample_policy.id)},
        headers=as_analyst,
    )
    assert res.status_code == 202

    name, claim_id, policy_id = queue.calls[-1]
    assert name == "audit_claim_task"
    assert claim_id == str(sample_claim.id)
    assert policy_id == str(sample_policy.id)


async def test_appeal_is_absent_until_generated(client, as_analyst, sample_claim):
    res = await client.get(f"/api/v1/claims/{sample_claim.id}/appeal", headers=as_analyst)
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"
