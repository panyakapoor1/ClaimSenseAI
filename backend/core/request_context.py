"""Per-request identity, carried without threading it through every signature.

A request id is the thread that ties an API call to the log lines it produced,
the error the caller saw, and (from P8) the audit_logs row it wrote. Holding it
in a ContextVar means service and repository code can record it without taking a
Request parameter it otherwise has no use for.
"""

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

REQUEST_ID_HEADER = "X-Request-ID"

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return _request_id.get()


def set_request_id(value: str) -> None:
    _request_id.set(value)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Adopt the caller's request id, or mint one, and echo it back.

    Honouring an inbound header matters as soon as anything sits in front of this
    service: a load balancer or the Next.js server can then correlate its own
    logs with ours instead of each inventing a separate id for one request.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request, call_next):
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming or uuid.uuid4().hex
        set_request_id(request_id)
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
