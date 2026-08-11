import json


async def publish_progress(ctx, job_id: str, data: dict):
    """Publish a progress update to Redis Pub/Sub for WebSocket streaming.

    The frontend (LiveTaskTracker) expects `type`, `status`, `message` and
    `progress_pct`, and treats status "completed" / "error" as terminal.
    """
    try:
        redis = ctx.get("redis") or ctx.get("pool")
        if redis:
            await redis.publish(f"job_updates:{job_id}", json.dumps(data))
    except Exception as e:
        print(f"Warning: Failed to publish progress: {e}")
