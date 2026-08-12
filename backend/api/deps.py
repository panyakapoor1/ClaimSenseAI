"""Shared route dependencies."""

from typing import Annotated, AsyncIterator

from fastapi import Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal


async def get_session() -> AsyncIterator[AsyncSession]:
    """One transaction per request, committed on success and rolled back on error.

    Routes previously opened their own sessions and committed mid-handler, so a
    failure after the first commit left a half-written claim behind. Scoping the
    transaction to the request makes a failed request leave nothing.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_queue(request: Request):
    """The arq pool, created once at startup and shared."""
    return request.app.state.redis_pool


QueueDep = Annotated[object, Depends(get_queue)]


class Pagination:
    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=100, description="Rows per page.")] = 25,
        cursor: Annotated[str | None, Query(description="Token from a previous page.")] = None,
    ):
        self.limit = limit
        self.cursor = cursor


PaginationDep = Annotated[Pagination, Depends(Pagination)]
