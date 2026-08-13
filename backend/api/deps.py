"""Shared route dependencies."""

import uuid
from typing import Annotated, AsyncIterator

from fastapi import Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.errors import UnauthenticatedError
from core.database import AsyncSessionLocal
from core.security import SESSION_COOKIE, InvalidToken, decode_access_token
from models import User
from services import auth as auth_service


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


def _extract_token(request: Request) -> str | None:
    """Read the session token from the cookie, falling back to the header.

    The browser uses an httpOnly cookie, which JavaScript cannot read and so an
    XSS bug cannot steal. Server Components run in a different container and
    cannot send that cookie, so they forward it as a bearer token instead.
    """
    cookie = request.cookies.get(SESSION_COOKIE)
    if cookie:
        return cookie

    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


async def get_current_user(request: Request, session: SessionDep) -> User:
    token = _extract_token(request)
    if not token:
        raise UnauthenticatedError("Sign in to continue.")

    try:
        claims = decode_access_token(token)
    except InvalidToken as e:
        raise UnauthenticatedError(str(e)) from e

    try:
        user_id = uuid.UUID(claims["sub"])
    except (KeyError, ValueError) as e:
        raise UnauthenticatedError("Malformed session token.") from e

    user = await auth_service.load_user(session, user_id)
    # Recorded on the request so audit logging and error reporting can attribute
    # the call without re-reading the token.
    request.state.user = user
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def requires(capability: str):
    """Build a dependency that enforces one capability.

    Enforcement lives on the server, in the route definition. The frontend hides
    controls a role cannot use, but that is presentation; this is the boundary.
    """

    async def _check(user: CurrentUser) -> User:
        auth_service.require_capability(user.role, capability)
        return user

    return Depends(_check)


class Pagination:
    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=100, description="Rows per page.")] = 25,
        cursor: Annotated[str | None, Query(description="Token from a previous page.")] = None,
    ):
        self.limit = limit
        self.cursor = cursor


PaginationDep = Annotated[Pagination, Depends(Pagination)]
