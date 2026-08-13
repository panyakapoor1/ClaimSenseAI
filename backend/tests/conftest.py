"""Test fixtures.

These are contract tests: they exercise the real app against the real database
and a stubbed queue. Mocking the database would let the schema and the API drift
apart silently, which is the specific failure the P2 gate exists to catch.

The queue is stubbed because enqueuing is the boundary of this phase: that a
job was queued with the right arguments is the contract; what the worker does
with it is tested where the worker is.
"""

import os
import sys
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from core.bootstrap import ensure_demo_tenant  # noqa: E402
from core.database import AsyncSessionLocal  # noqa: E402
from main import app  # noqa: E402
from models import Claim, ClaimStatus, Organization, Policy, User, UserRole  # noqa: E402
from services import auth as auth_service  # noqa: E402


class StubJob:
    def __init__(self, job_id: str):
        self.job_id = job_id


class StubQueue:
    """Records enqueue calls instead of talking to Redis."""

    def __init__(self):
        self.calls: list[tuple] = []

    async def enqueue_job(self, name, *args):
        self.calls.append((name, *args))
        return StubJob(f"stub-{len(self.calls)}")

    async def ping(self):
        return True


@pytest_asyncio.fixture(autouse=True)
async def _dispose_engine():
    """Drop pooled connections between tests.

    The engine is created once at import, but pytest-asyncio runs each test in a
    fresh event loop. A pooled asyncpg connection belongs to the loop that opened
    it, so reusing one in the next test raises "attached to a different loop".
    Disposing after each test means every test opens its own connections.
    """
    yield
    from core.database import engine

    await engine.dispose()


@pytest.fixture
def queue() -> StubQueue:
    return StubQueue()


@pytest_asyncio.fixture
async def client(queue) -> AsyncClient:
    """An HTTP client bound to the app, with lifespan bypassed.

    Startup would open a real Redis pool; the stub replaces it, so the tests do
    not require the queue to be running.
    """
    app.state.redis_pool = queue
    app.state.redis_pubsub = None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def session():
    async with AsyncSessionLocal() as s:
        yield s


async def _auth_header(session, role: UserRole) -> dict[str, str]:
    """A bearer header for the demo user holding `role`.

    Uses the real token issuer rather than a hand-built token, so the tests
    exercise the same signing and decoding path production does.
    """
    org, _ = await ensure_demo_tenant(session)
    await session.commit()

    user = (
        await session.execute(
            select(User).where(User.organization_id == org.id, User.role == role)
        )
    ).scalars().first()
    assert user is not None, f"no seeded demo user with role {role}"

    token, _ttl = auth_service.issue_token(user)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def as_analyst(session):
    return await _auth_header(session, UserRole.ANALYST)


@pytest_asyncio.fixture
async def as_senior(session):
    return await _auth_header(session, UserRole.SENIOR_ANALYST)


@pytest_asyncio.fixture
async def as_admin(session):
    return await _auth_header(session, UserRole.ADMIN)


@pytest_asyncio.fixture
async def as_auditor(session):
    return await _auth_header(session, UserRole.AUDITOR)


@pytest_asyncio.fixture
async def foreign_org(session):
    """A second tenant, so cross-organization isolation can be tested for real.

    Without this the scoping tests would pass trivially, because every row would belong
    to the only organization that exists.
    """
    # Id assigned here rather than relying on a post-commit refresh, so the
    # dependent fixtures below always see a populated value.
    org = Organization(
        id=uuid.uuid4(), name="Rival Health TPA", slug=f"rival-{uuid.uuid4().hex[:8]}"
    )
    session.add(org)
    await session.commit()
    await session.refresh(org)

    yield org

    await session.delete(org)
    await session.commit()


@pytest_asyncio.fixture
async def foreign_claim(session, foreign_org):
    claim = Claim(
        id=uuid.uuid4(),
        organization_id=foreign_org.id,
        reference=f"CLM-RIVAL-{uuid.uuid4().hex[:6].upper()}",
        total_billed=9999.0,
        status=ClaimStatus.AUDIT_COMPLETE,
    )
    session.add(claim)
    await session.commit()
    await session.refresh(claim)

    yield claim

    # Removed before the owning organization is torn down. Without this,
    # deleting the org makes SQLAlchemy null the child's organization_id, which
    # the NOT NULL constraint rejects, failing teardown for a passing test.
    await session.delete(claim)
    await session.commit()


@pytest_asyncio.fixture
async def foreign_policy(session, foreign_org):
    policy = Policy(
        id=uuid.uuid4(),
        organization_id=foreign_org.id,
        insurer_name="Rival Insurer",
        policy_name="Rival Plan",
    )
    session.add(policy)
    await session.commit()
    await session.refresh(policy)

    yield policy

    await session.delete(policy)
    await session.commit()


@pytest_asyncio.fixture
async def sample_claim(session):
    """A throwaway claim, removed afterwards so tests do not accumulate rows."""
    org, user = await ensure_demo_tenant(session)
    claim = Claim(
        organization_id=org.id,
        created_by_id=user.id if user else None,
        reference=f"CLM-TEST-{uuid.uuid4().hex[:6].upper()}",
        total_billed=1000.0,
        status=ClaimStatus.AUDIT_COMPLETE,
    )
    session.add(claim)
    await session.commit()
    await session.refresh(claim)

    yield claim

    await session.delete(claim)
    await session.commit()


@pytest_asyncio.fixture
async def sample_policy(session):
    org, _ = await ensure_demo_tenant(session)
    policy = Policy(
        organization_id=org.id,
        insurer_name="Test Insurer",
        policy_name="Test Plan",
    )
    session.add(policy)
    await session.commit()
    await session.refresh(policy)

    yield policy

    await session.delete(policy)
    await session.commit()


MINIMAL_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"
)
