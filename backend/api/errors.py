"""One error shape for every failure the API can produce.

The prototype returned FastAPI's default `{"detail": ...}` for HTTPException, a
different shape for validation errors, and an HTML traceback for anything
unhandled. A client had no single thing to parse, so the frontend ended up
matching on HTTP status alone and showing "An error occurred".

Every error now serialises as:

    {"error": {"code": "...", "message": "...", "details": ..., "request_id": "..."}}
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.request_context import get_request_id

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base for errors the API raises deliberately.

    Services raise these instead of HTTPException so that the domain layer does
    not import the web framework and stays usable from the worker.
    """

    status_code = 500
    code = "internal_error"
    message = "An unexpected error occurred."

    def __init__(self, message: str | None = None, *, details=None):
        super().__init__(message or self.message)
        if message:
            self.message = message
        self.details = details


class NotFoundError(APIError):
    status_code = 404
    code = "not_found"
    message = "The requested resource does not exist."


class ValidationError(APIError):
    status_code = 422
    code = "validation_failed"
    message = "The request was not valid."


class UnauthenticatedError(APIError):
    status_code = 401
    code = "unauthenticated"
    message = "Authentication is required."


class ForbiddenError(APIError):
    """Authenticated, but not permitted.

    Distinct from 401 on purpose: the client should not retry with different
    credentials, and the UI should say "you cannot do this" rather than
    bouncing the user back to a login screen they just came from.
    """

    status_code = 403
    code = "forbidden"
    message = "You do not have permission to perform this action."


class RateLimitedError(APIError):
    status_code = 429
    code = "rate_limited"
    message = "Too many requests. Please slow down."


class ConflictError(APIError):
    status_code = 409
    code = "conflict"
    message = "The request conflicts with the current state of the resource."


class DependencyUnavailableError(APIError):
    """A service we depend on (queue, model provider) is not usable right now."""

    status_code = 503
    code = "dependency_unavailable"
    message = "A required downstream service is unavailable."


def error_body(code: str, message: str, details=None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": get_request_id(),
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def _api_error(request: Request, exc: APIError):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        # Covers 404s raised by the router itself, not just our own raises.
        code = {400: "bad_request", 401: "unauthenticated", 403: "forbidden",
                404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, str(exc.detail)),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=error_body(
                "validation_failed",
                "The request was not valid.",
                # `errors()` contains non-JSON-serialisable context objects in
                # some cases, so reduce it to the fields a client can act on.
                details=[
                    {"field": ".".join(str(p) for p in e["loc"]), "reason": e["msg"]}
                    for e in exc.errors()
                ],
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        # Logged with the request id so the traceback can be found from the
        # opaque response the caller received.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=error_body("internal_error", "An unexpected error occurred."),
        )


# Re-exported so app assembly can document the shared error shape without
# importing from schemas/, which imports models/ and would create a cycle.
from schemas.common import ErrorResponse  # noqa: E402
