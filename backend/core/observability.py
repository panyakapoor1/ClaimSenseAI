"""Request timing middleware feeding the metrics registry."""

import time

from starlette.middleware.base import BaseHTTPMiddleware

from core.metrics import metrics


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            # The templated path, not the resolved one: labelling by
            # /api/v1/claims/{claim_id} keeps cardinality bounded, where the
            # literal URL would create a new time series per claim.
            route = request.scope.get("route")
            path = getattr(route, "path", request.url.path)
            metrics.observe(request.method, path, status, time.perf_counter() - started)
