import pytest

pytestmark = pytest.mark.asyncio


async def test_health_is_liveness_only(client):
    """Liveness must not depend on external services."""
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


async def test_ready_reports_each_dependency(client):
    res = await client.get("/ready")
    assert res.status_code in (200, 503)

    body = res.json()
    assert set(body["checks"]) == {"database", "queue", "llm"}
    # The database must be reachable for the rest of the suite to mean anything.
    assert body["checks"]["database"]["ok"] is True


async def test_ready_marks_llm_as_optional(client):
    """An absent model provider is degraded, not unready."""
    body = (await client.get("/ready")).json()
    assert body["checks"]["llm"]["required"] is False


async def test_metrics_are_prometheus_formatted(client):
    await client.get("/health")
    res = await client.get("/metrics")

    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/plain")

    body = res.text
    assert "# TYPE claimsense_http_requests_total counter" in body
    assert "claimsense_http_request_duration_seconds_bucket" in body
    # The /health call above must have been counted.
    assert 'route="/health"' in body


async def test_request_id_is_echoed(client):
    res = await client.get("/health")
    assert res.headers.get("X-Request-ID")


async def test_inbound_request_id_is_honoured(client):
    """A caller's correlation id survives, rather than being replaced."""
    res = await client.get("/health", headers={"X-Request-ID": "caller-supplied-id"})
    assert res.headers["X-Request-ID"] == "caller-supplied-id"
