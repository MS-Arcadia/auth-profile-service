import asyncio
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

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


@router.websocket("/ws/presence")
async def presence_heartbeat(websocket: WebSocket, token: str = Query(...)):
    jwt_provider = get_jwt_provider()
    try:
        claims = jwt_provider.decode_access_token(token)
    except TokenError:
        await websocket.close(code=4401)
        return

    user_id = claims["sub"]
    await websocket.accept()

    presence_store: RedisPresenceStore = websocket.app.state.presence_store
    event_publisher: KafkaEventPublisher = websocket.app.state.event_publisher
    use_case = UpdatePresenceUseCase(presence_store, event_publisher)

    try:
        await use_case.execute(user_id)
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=PRESENCE_TTL_SECONDS)
            except TimeoutError:
                break
            await use_case.execute(user_id)
    except WebSocketDisconnect:
        logger.info("Presence WebSocket disconnected for user_id=%s", user_id)
    finally:
        pass
