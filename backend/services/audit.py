"""Writing to the append-only audit trail.

P1 created `audit_logs` with a trigger that rejects UPDATE and DELETE. This is
the only sanctioned way to add to it.

Failures here are logged, never raised: an audit write must not be able to fail
the operation it is recording. Losing one log line is bad; rolling back a
successful login because the log write failed is worse.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from core.request_context import get_request_id
from models import AuditLog, User

logger = logging.getLogger(__name__)


async def record_audit(
    session: AsyncSession,
    *,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
    request=None,
) -> None:
    """Append one entry describing a privileged action."""
    try:
        client_host = None
        user_agent = None
        if request is not None:
            client_host = getattr(getattr(request, "client", None), "host", None)
            user_agent = request.headers.get("user-agent")

        session.add(
            AuditLog(
                actor_id=actor.id if actor else None,
                organization_id=actor.organization_id if actor else None,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                before=before,
                after=after,
                ip_address=client_host,
                user_agent=user_agent[:500] if user_agent else None,
                request_id=get_request_id(),
            )
        )
        await session.flush()
    except Exception:
        logger.exception("Failed to write audit entry for action=%s", action)
