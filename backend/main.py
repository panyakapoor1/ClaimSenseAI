"""Application assembly.

This module wires the app together and does nothing else. Request handling lives
in api/, use cases in services/, persistence in models/. The prototype's main.py
held all three, which is why a schema change meant editing route handlers.
"""

import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from arq import create_pool
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.errors import ErrorResponse, register_exception_handlers
from api.ops import router as ops_router
from api.v1 import api_router
from api.ws import router as ws_router
from core.bootstrap import ensure_demo_tenant
from core.config import get_redis_settings, settings
from core.database import AsyncSessionLocal
from core.observability import MetricsMiddleware
from core.request_context import RequestIDMiddleware
from schemas.ops import ServiceBanner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("claimsense")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ClaimSense AI backend starting")
    app.state.redis_pool = await create_pool(get_redis_settings())
    app.state.redis_pubsub = aioredis.from_url(settings.redis_url, decode_responses=True)

    # Ownership columns are required, so a real tenant must exist before any
    # upload can be attributed. Idempotent; P3 replaces this with real signup.
    async with AsyncSessionLocal() as session:
        org, user = await ensure_demo_tenant(session)
        await session.commit()
        logger.info("Demo tenant ready: org=%s analyst=%s", org.slug, user.email if user else "none")

    yield

    logger.info("ClaimSense AI backend shutting down")
    await app.state.redis_pubsub.close()
    app.state.redis_pool.close()
    await app.state.redis_pool.wait_closed()


app = FastAPI(
    title="ClaimSense AI",
    description=(
        "Claims intelligence API. Adjudicates hospital bills line by line against "
        "the governing policy, with every verdict traceable to the clause it rests on."
    ),
    version="2.0.0",
    lifespan=lifespan,
    # Documented once here rather than repeated on every route.
    responses={
        400: {"model": ErrorResponse, "description": "Malformed request"},
        404: {"model": ErrorResponse, "description": "Resource does not exist"},
        409: {"model": ErrorResponse, "description": "Conflicts with current state"},
        422: {"model": ErrorResponse, "description": "Validation failed"},
        500: {"model": ErrorResponse, "description": "Unexpected server error"},
        503: {"model": ErrorResponse, "description": "A dependency is unavailable"},
    },
)

# Order matters: the request id must be set before anything that records it, and
# metrics must wrap the handler to time it.
app.add_middleware(MetricsMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

register_exception_handlers(app)

app.include_router(ops_router)
app.include_router(api_router)
app.include_router(ws_router)


@app.get("/", tags=["ops"], response_model=ServiceBanner, summary="Service banner")
async def root():
    return {"service": "ClaimSense AI API", "version": app.version, "docs": "/docs"}
