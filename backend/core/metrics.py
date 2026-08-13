"""Minimal in-process metrics, exposed in Prometheus text format.

Hand-rolled rather than pulling in prometheus_client: what P2 needs is request
counts and latency, the exposition format is a few lines, and adding a
dependency for that would fail the project's own technology test. If P12 needs
exemplars, multiprocess collection or custom collectors, swap this for the real
library then; `/metrics` is the only thing that would change.

Every number here is measured. Nothing is estimated or seeded.
"""

import threading
import time
from collections import defaultdict

# Seconds. Chosen around the shapes this API actually has: sub-100ms reads, and
# uploads that run to a few seconds.
LATENCY_BUCKETS = (0.005, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: dict[tuple[str, str, int], int] = defaultdict(int)
        self._duration_sum: dict[tuple[str, str], float] = defaultdict(float)
        self._duration_count: dict[tuple[str, str], int] = defaultdict(int)
        self._duration_buckets: dict[tuple[str, str, float], int] = defaultdict(int)
        self._started = time.time()

    def observe(self, method: str, route: str, status: int, seconds: float) -> None:
        with self._lock:
            self._requests[(method, route, status)] += 1
            self._duration_sum[(method, route)] += seconds
            self._duration_count[(method, route)] += 1
            for bound in LATENCY_BUCKETS:
                if seconds <= bound:
                    self._duration_buckets[(method, route, bound)] += 1

    def render(self) -> str:
        lines: list[str] = []
        with self._lock:
            lines.append("# HELP claimsense_uptime_seconds Seconds since process start.")
            lines.append("# TYPE claimsense_uptime_seconds gauge")
            lines.append(f"claimsense_uptime_seconds {time.time() - self._started:.3f}")

            lines.append("# HELP claimsense_http_requests_total Total HTTP requests.")
            lines.append("# TYPE claimsense_http_requests_total counter")
            for (method, route, status), count in sorted(self._requests.items()):
                lines.append(
                    f'claimsense_http_requests_total{{method="{method}",'
                    f'route="{route}",status="{status}"}} {count}'
                )

            lines.append("# HELP claimsense_http_request_duration_seconds Request latency.")
            lines.append("# TYPE claimsense_http_request_duration_seconds histogram")
            for (method, route), count in sorted(self._duration_count.items()):
                cumulative = 0
                for bound in LATENCY_BUCKETS:
                    cumulative = self._duration_buckets.get((method, route, bound), 0)
                    lines.append(
                        f'claimsense_http_request_duration_seconds_bucket{{method="{method}",'
                        f'route="{route}",le="{bound}"}} {cumulative}'
                    )
                lines.append(
                    f'claimsense_http_request_duration_seconds_bucket{{method="{method}",'
                    f'route="{route}",le="+Inf"}} {count}'
                )
                lines.append(
                    f'claimsense_http_request_duration_seconds_sum{{method="{method}",'
                    f'route="{route}"}} {self._duration_sum[(method, route)]:.6f}'
                )
                lines.append(
                    f'claimsense_http_request_duration_seconds_count{{method="{method}",'
                    f'route="{route}"}} {count}'
                )

        return "\n".join(lines) + "\n"


metrics = Metrics()
