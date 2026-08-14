import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.application.use_cases.profile.update_presence import (
    PRESENCE_TTL_SECONDS,
    UpdatePresenceUseCase,
)
from app.core.security_deps import get_jwt_provider
from app.domain.auth.exceptions import TokenError
from app.infrastructure.cache.redis_presence_store import RedisPresenceStore
from app.infrastructure.messaging.kafka_producer import KafkaEventPublisher

router = APIRouter(tags=["Presence"])
logger = logging.getLogger(__name__)

HEARTBEAT_EXPECTED_INTERVAL = 10

# How long the first frame — the one carrying the token — may take to arrive. Short,
# because a client that has just been accepted has nothing else to do first, and an
# unauthenticated socket should not be held open while somebody decides.
AUTH_FRAME_TIMEOUT_SECONDS = 5

# Closing codes, from the private-use range. 4401 is "that token is not usable".
CLOSE_UNAUTHENTICATED = 4401


@router.websocket("/ws/presence")
async def presence_heartbeat(websocket: WebSocket):
    """Keep a person marked online for as long as they have a tab open.

    The token arrives as the **first message**, not as a query parameter.

    A browser cannot set headers on a WebSocket handshake, so the usual way to
    authenticate one is `?token=`, and that is what this route used to do. The cost is
    that the credential is then part of a URL: uvicorn writes the full request line to its
    access log, those logs ship to Loki, and anyone who can read a dashboard can read a
    live access token out of it. A URL is also the one part of a request that ends up in
    proxy logs and browser history without anybody deciding it should.

    Sending it in the first frame keeps it out of all of those, at the cost of accepting
    the connection before knowing who it is — which is bounded here to five seconds and
    one frame.
    """
    await websocket.accept()

    try:
        token = await asyncio.wait_for(websocket.receive_text(), timeout=AUTH_FRAME_TIMEOUT_SECONDS)
    except (TimeoutError, WebSocketDisconnect):
        await websocket.close(code=CLOSE_UNAUTHENTICATED)
        return

    try:
        claims = get_jwt_provider().decode_access_token(token)
    except TokenError:
        await websocket.close(code=CLOSE_UNAUTHENTICATED)
        return

    user_id = claims["sub"]

    presence_store: RedisPresenceStore = websocket.app.state.presence_store
    event_publisher: KafkaEventPublisher = websocket.app.state.event_publisher
    use_case = UpdatePresenceUseCase(presence_store, event_publisher)

    try:
        await use_case.execute(user_id)
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=PRESENCE_TTL_SECONDS)
            except TimeoutError:
                # No heartbeat within the TTL. The key is about to expire anyway, so there
                # is nothing to clean up — letting go is the whole of "went offline".
                break
            await use_case.execute(user_id)
    except WebSocketDisconnect:
        logger.info("Presence WebSocket disconnected for user_id=%s", user_id)
