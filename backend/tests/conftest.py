"""Test fixtures.

These are contract tests: they exercise the real app against the real database
and a stubbed queue. Mocking the database would let the schema and the API drift
apart silently, which is the specific failure the P2 gate exists to catch.

The queue is stubbed because enqueuing is the boundary of this phase — that a
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

from core.database import AsyncSessionLocal  # noqa: E402
from main import app  # noqa: E402
from models import Claim, ClaimStatus, Policy  # noqa: E402
from core.bootstrap import ensure_demo_tenant, new_claim_reference  # noqa: E402


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
