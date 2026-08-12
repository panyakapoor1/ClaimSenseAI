"""Live job progress over WebSocket.

Unversioned alongside the ops endpoints: the frame shape is owned by the worker's
progress publisher, not by the REST contract.
"""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from core.database import AsyncSessionLocal
from core.security import SESSION_COOKIE, InvalidToken, decode_access_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["realtime"])

# Sent before closing so the client can distinguish "you are signed out" from a
# dropped connection. The prototype closed silently, and the frontend rendered
# every closure as "WebSocket error: {}".
POLICY_VIOLATION = 1008


async def _authenticate(websocket: WebSocket):
    """Resolve the caller from the session cookie, or None.

    Cookies are scoped by host and ignore port, so the httpOnly cookie the API
    set on localhost is sent with this handshake automatically. A bearer token is
    also accepted for non-browser clients.
    """
    token = websocket.cookies.get(SESSION_COOKIE)
    if not token:
        header = websocket.headers.get("authorization", "")
        if header.lower().startswith("bearer "):
            token = header[7:].strip()

    if not token:
        return None

    try:
        claims = decode_access_token(token)
    except InvalidToken:
        return None

    from services.auth import load_user
    import uuid as _uuid

    try:
        async with AsyncSessionLocal() as session:
            return await load_user(session, _uuid.UUID(claims["sub"]))
    except Exception:
        return None


@router.websocket("/ws/tasks/{job_id}")
async def task_updates(websocket: WebSocket, job_id: str):
    """Relay Redis pub/sub progress for one job to one signed-in client.

    Progress frames quote line-item descriptions from the bill, so this stream
    carries claim content and must not be readable by anyone who guesses a job id.
    """
    await websocket.accept()

    user = await _authenticate(websocket)
    if user is None:
        await websocket.send_json(
            {"type": "error", "status": "error", "message": "Sign in to follow this job."}
        )
        await websocket.close(code=POLICY_VIOLATION)
        return

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
    except Exception:
        logger.exception("WebSocket relay failed for job %s", job_id)
    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
        except Exception:
            logger.debug("Pub/sub cleanup failed for job %s", job_id, exc_info=True)

        # Breaking out of the loop leaves the socket open otherwise, and the
        # client sits waiting on a stream that will never produce another frame.
        if websocket.client_state is not WebSocketState.DISCONNECTED:
            try:
                await websocket.close()
            except RuntimeError:
                pass  # already closed by the client disconnecting
