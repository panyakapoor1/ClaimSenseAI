"""Every failure must serialise as the same envelope."""

import uuid

import pytest

pytestmark = pytest.mark.asyncio


def assert_envelope(body, expected_code):
    assert "error" in body, f"expected error envelope, got {body}"
    error = body["error"]
    assert set(error) == {"code", "message", "details", "request_id"}
    assert error["code"] == expected_code
    assert isinstance(error["message"], str) and error["message"]
    assert error["request_id"], "errors must carry a request id for correlation"


async def test_unknown_claim_returns_not_found_envelope(client, as_analyst):
    res = await client.get(f"/api/v1/claims/{uuid.uuid4()}", headers=as_analyst)
    assert res.status_code == 404
    assert_envelope(res.json(), "not_found")


async def test_unknown_route_returns_envelope(client, as_analyst):
    """Router-generated 404s use the same shape as ones we raise."""
    res = await client.get("/api/v1/nonexistent", headers=as_analyst)
    assert res.status_code == 404
    assert_envelope(res.json(), "not_found")


async def test_malformed_uuid_is_a_validation_error(client, as_analyst):
    res = await client.get("/api/v1/claims/not-a-uuid", headers=as_analyst)
    assert res.status_code == 422
    body = res.json()
    assert_envelope(body, "validation_failed")
    assert body["error"]["details"], "validation errors must say which field failed"
    assert "claim_id" in body["error"]["details"][0]["field"]


async def test_pagination_limit_is_bounded(client, as_analyst):
    res = await client.get("/api/v1/claims?limit=5000", headers=as_analyst)
    assert res.status_code == 422
    assert_envelope(res.json(), "validation_failed")


async def test_malformed_cursor_is_rejected(client, as_analyst):
    res = await client.get("/api/v1/claims?cursor=!!!not-base64!!!", headers=as_analyst)
    assert res.status_code == 422
    assert_envelope(res.json(), "validation_failed")


async def test_appeal_before_audit_is_a_conflict(client, as_analyst, session):
    """State-machine violations are 409, distinct from 404 and 422."""
    from core.bootstrap import ensure_demo_tenant, new_claim_reference
    from models import Claim, ClaimStatus

    org, user = await ensure_demo_tenant(session)
    claim = Claim(
        organization_id=org.id,
        created_by_id=user.id if user else None,
        reference=new_claim_reference(),
        status=ClaimStatus.RECEIVED,
    )
    session.add(claim)
    await session.commit()

    try:
        res = await client.post(f"/api/v1/claims/{claim.id}/appeal", headers=as_analyst)
        assert res.status_code == 409
        assert_envelope(res.json(), "conflict")
    finally:
        await session.delete(claim)
        await session.commit()
