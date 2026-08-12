"""Operational endpoints.

Unversioned on purpose: these describe the process, not the product API, and the
things that scrape them (orchestrators, uptime checks, Prometheus) should not
have to follow product API versioning.
"""

import asyncio

from fastapi import APIRouter, Request, Response
from sqlalchemy import text

from core.database import AsyncSessionLocal
from core.llm import LLM_AVAILABLE, LLM_MODEL
from core.metrics import metrics
from services import storage
from schemas.ops import HealthResponse, ReadyResponse

router = APIRouter(tags=["ops"])


@router.get("/health", response_model=HealthResponse, summary="Liveness")
async def health():
    """Is the process up? Deliberately checks nothing external.

    A liveness probe that fails when the database is briefly unreachable causes
    the orchestrator to restart a healthy process, which does not help.
    """
    return {"status": "healthy", "llm_available": LLM_AVAILABLE, "llm_model": LLM_MODEL if LLM_AVAILABLE else None}


@router.get("/ready", response_model=ReadyResponse, summary="Readiness")
async def ready(request: Request, response: Response):
    """Can this process actually serve traffic?

    Checks each dependency independently and reports them separately, so a
    failing readiness probe says which one is down instead of just "not ready".
    """
    checks: dict[str, dict] = {}

    async def check(name: str, coro):
        try:
            await asyncio.wait_for(coro, timeout=3)
            checks[name] = {"ok": True}
        except Exception as e:
            checks[name] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

    async def _db():
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))

    async def _queue():
        pool = getattr(request.app.state, "redis_pool", None)
        if pool is None:
            raise RuntimeError("Queue pool was never initialised.")
        await pool.ping()

    async def _storage():
        # A round-trip, not just a connection: a reachable endpoint with an
        # unwritable bucket is not actually ready.
        import asyncio as _asyncio

        probe_key = "_healthcheck/probe"
        await _asyncio.to_thread(storage.put, probe_key, b"ok", content_type="text/plain")
        await _asyncio.to_thread(storage.get, probe_key)

    await check("database", _db())
    await check("queue", _queue())
    await check("storage", _storage())
    checks["storage"].update(storage.describe())

    # The LLM is reported but not required: the API still serves reads and
    # accepts uploads without it, so an absent key is degraded, not unready.
    checks["llm"] = {"ok": LLM_AVAILABLE, "required": False}

    ready_now = all(c["ok"] for name, c in checks.items() if c.get("required", True))
    response.status_code = 200 if ready_now else 503
    return {"ready": ready_now, "checks": checks}


@router.get("/metrics", summary="Prometheus metrics", response_class=Response)
async def prometheus_metrics():
    return Response(content=metrics.render(), media_type="text/plain; version=0.0.4")
