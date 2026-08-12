"""Live job progress over WebSocket.

Unversioned alongside the ops endpoints: the frame shape is owned by the worker's
progress publisher, not by the REST contract.
"""

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/tasks/{job_id}")
async def task_updates(websocket: WebSocket, job_id: str):
    """Relay Redis pub/sub progress for one job to one client."""
    await websocket.accept()
    pubsub = websocket.app.state.redis_pubsub.pubsub()
    channel = f"job_updates:{job_id}"

    try:
        await pubsub.subscribe(channel)
        await websocket.send_json({"type": "connected", "job_id": job_id})

        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                data = json.loads(message["data"])
                await websocket.send_json(data)
                if data.get("status") in ("completed", "error"):
                    break
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        # Breaking out of the loop leaves the socket open otherwise, and the
        # client sits waiting on a stream that will never produce another frame.
        try:
            await websocket.close()
        except RuntimeError:
            pass  # already closed by the client disconnecting
