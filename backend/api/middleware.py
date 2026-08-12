"""Edge protections: response hardening and request throttling."""

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from api.errors import error_body

# Headers that cost nothing and remove whole classes of browser-side attack.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # This API returns JSON and never renders HTML, so everything can be denied.
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}

# The interactive docs are the one HTML surface, and they legitimately need to
# load Swagger's assets and inline styles.
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if not request.url.path.startswith(DOCS_PATHS):
            for header, value in SECURITY_HEADERS.items():
                response.headers.setdefault(header, value)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window-free sliding limiter, per client IP.

    In-process and therefore per-replica: it throttles a single abusive client,
    it is not a distributed quota. A Redis-backed limiter belongs with the rest
    of the deployment work; this closes the "no rate limiting at all" gap now.

    Login is limited far more tightly than everything else, because that is the
    endpoint worth guessing against.
    """

    def __init__(self, app, *, default_limit: int = 300, auth_limit: int = 10, window: int = 60):
        super().__init__(app)
        self.default_limit = default_limit
        self.auth_limit = auth_limit
        self.window = window
        self._hits: dict[tuple[str, str], deque] = defaultdict(deque)

    def _limit_for(self, path: str) -> tuple[str, int]:
        if path.startswith("/api/v1/auth/login"):
            return "auth", self.auth_limit
        return "default", self.default_limit

    async def dispatch(self, request, call_next):
        # Probes and scrapes run on a schedule and would consume the budget.
        if request.url.path in ("/health", "/ready", "/metrics"):
            return await call_next(request)

        bucket, limit = self._limit_for(request.url.path)
        client = getattr(request.client, "host", "unknown")
        key = (client, bucket)

        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window:
            hits.popleft()

        if len(hits) >= limit:
            retry_after = int(self.window - (now - hits[0])) + 1
            return JSONResponse(
                status_code=429,
                content=error_body(
                    "rate_limited",
                    f"Too many requests. Try again in {retry_after} seconds.",
                ),
                headers={"Retry-After": str(retry_after)},
            )

        hits.append(now)
        return await call_next(request)
