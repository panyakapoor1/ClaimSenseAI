"""The authorization matrix.

Proves three things the frontend cannot be trusted to enforce:

  1. Every protected route rejects an anonymous caller.
  2. Each role is allowed exactly what the permission table says, no more.
  3. No role can read another organization's data, regardless of capability.
"""

import uuid

import pytest

from models import UserRole
from services import auth as auth_service


PROTECTED_ROUTES = [
    ("GET", "/api/v1/claims"),
    ("POST", "/api/v1/claims"),
    ("GET", f"/api/v1/claims/{uuid.uuid4()}"),
    ("POST", f"/api/v1/claims/{uuid.uuid4()}/audit"),
    ("POST", f"/api/v1/claims/{uuid.uuid4()}/appeal"),
    ("GET", f"/api/v1/claims/{uuid.uuid4()}/appeal"),
    ("GET", "/api/v1/policies"),
    ("POST", "/api/v1/policies"),
    ("GET", f"/api/v1/policies/{uuid.uuid4()}/clauses?q=room+rent"),
    ("GET", "/api/v1/auth/me"),
]


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
async def test_anonymous_is_rejected(client, method, path):
    """No protected route may be reachable without a session."""
    res = await client.request(method, path)
    assert res.status_code == 401, f"{method} {path} allowed an anonymous caller"
    assert res.json()["error"]["code"] == "unauthenticated"


async def test_expired_or_forged_token_is_rejected(client):
    res = await client.get(
        "/api/v1/claims", headers={"Authorization": "Bearer not.a.real.token"}
    )
    assert res.status_code == 401


# (role, capability, expected)
CAPABILITY_MATRIX = [
    (UserRole.ANALYST, auth_service.READ_CLAIMS, True),
    (UserRole.ANALYST, auth_service.CREATE_CLAIMS, True),
    (UserRole.ANALYST, auth_service.RUN_ANALYSIS, True),
    (UserRole.ANALYST, auth_service.DECIDE_CLAIMS, False),
    (UserRole.ANALYST, auth_service.ADMINISTER, False),

    (UserRole.SENIOR_ANALYST, auth_service.RUN_ANALYSIS, True),
    (UserRole.SENIOR_ANALYST, auth_service.DECIDE_CLAIMS, True),
    (UserRole.SENIOR_ANALYST, auth_service.ADMINISTER, False),

    (UserRole.ADMIN, auth_service.ADMINISTER, True),
    (UserRole.ADMIN, auth_service.READ_CLAIMS, True),
    # Administering the platform is not adjudicating a claim.
    (UserRole.ADMIN, auth_service.DECIDE_CLAIMS, False),

    (UserRole.AUDITOR, auth_service.READ_CLAIMS, True),
    (UserRole.AUDITOR, auth_service.CREATE_CLAIMS, False),
    (UserRole.AUDITOR, auth_service.RUN_ANALYSIS, False),
    (UserRole.AUDITOR, auth_service.DECIDE_CLAIMS, False),
    (UserRole.AUDITOR, auth_service.MANAGE_POLICIES, False),
]


@pytest.mark.parametrize("role,capability,expected", CAPABILITY_MATRIX)
def test_capability_table(role, capability, expected):
    assert auth_service.can(role, capability) is expected


async def test_auditor_can_read_claims(client, as_auditor):
    res = await client.get("/api/v1/claims", headers=as_auditor)
    assert res.status_code == 200


async def test_auditor_cannot_create_claims(client, as_auditor, queue):
    """Read-only oversight must stay read-only, at the server."""
    before = len(queue.calls)
    res = await client.post(
        "/api/v1/claims",
        files={"file": ("bill.pdf", b"%PDF-1.4 minimal", "application/pdf")},
        headers=as_auditor,
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "forbidden"
    assert len(queue.calls) == before


async def test_auditor_cannot_run_an_audit(client, as_auditor, sample_claim, sample_policy):
    res = await client.post(
        f"/api/v1/claims/{sample_claim.id}/audit",
        json={"policy_id": str(sample_policy.id)},
        headers=as_auditor,
    )
    assert res.status_code == 403


async def test_auditor_cannot_upload_policies(client, as_auditor):
    res = await client.post(
        "/api/v1/policies",
        files={"file": ("policy.pdf", b"%PDF-1.4 minimal", "application/pdf")},
        headers=as_auditor,
    )
    assert res.status_code == 403


async def test_analyst_can_run_an_audit(client, as_analyst, sample_claim, sample_policy):
    res = await client.post(
        f"/api/v1/claims/{sample_claim.id}/audit",
        json={"policy_id": str(sample_policy.id)},
        headers=as_analyst,
    )
    assert res.status_code == 202


async def test_forbidden_is_distinct_from_unauthenticated(client, as_auditor):
    """403 must not masquerade as 401, or the UI bounces users to a pointless login."""
    anon = await client.post(
        "/api/v1/policies",
        files={"file": ("p.pdf", b"%PDF-1.4", "application/pdf")},
    )
    denied = await client.post(
        "/api/v1/policies",
        files={"file": ("p.pdf", b"%PDF-1.4", "application/pdf")},
        headers=as_auditor,
    )
    assert anon.status_code == 401
    assert denied.status_code == 403


async def test_cannot_read_another_organizations_claim(client, as_analyst, foreign_claim):
    """Cross-tenant isolation, the check that matters most.

    Reported as 404 rather than 403 on purpose: a 403 would confirm the id is
    real, letting an outsider enumerate which claims exist.
    """
    res = await client.get(f"/api/v1/claims/{foreign_claim.id}", headers=as_analyst)
    assert res.status_code == 404


async def test_another_organizations_claim_is_absent_from_the_list(
    client, as_analyst, foreign_claim
):
    res = await client.get("/api/v1/claims?limit=100", headers=as_analyst)
    references = [i["reference"] for i in res.json()["items"]]
    assert foreign_claim.reference not in references


async def test_cannot_audit_against_another_organizations_policy(
    client, as_analyst, sample_claim, foreign_policy, queue
):
    before = len(queue.calls)
    res = await client.post(
        f"/api/v1/claims/{sample_claim.id}/audit",
        json={"policy_id": str(foreign_policy.id)},
        headers=as_analyst,
    )
    assert res.status_code == 404
    assert len(queue.calls) == before
