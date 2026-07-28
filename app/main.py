import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.infrastructure.observability.logging_config import configure_logging
from app.infrastructure.observability.tracing import configure_tracing
from app.infrastructure.observability.metrics import configure_metrics
from app.core.middleware import CorrelationIdMiddleware
from app.core.exceptions import register_exception_handlers

from app.infrastructure.db.session import engine
from app.infrastructure.db.base import Base
from app.infrastructure.db.bootstrap import seed_super_admin

from app.infrastructure.db.models import (  
    user_model, role_request_model, login_audit_model, outbox_model, profile_models,
)

from app.infrastructure.messaging.kafka_producer import KafkaEventPublisher
from app.infrastructure.messaging.outbox_dispatcher import OutboxDispatcher
from app.infrastructure.messaging.kafka_consumer_base import KafkaConsumerBase
from app.infrastructure.messaging.consumers.abuse_event_consumer import AbuseEventConsumer
from app.infrastructure.messaging.consumers.profile_event_consumers import (
    handle_user_registered, handle_ownership_granted, handle_item_or_trade_event, handle_post_reacted,
)
from app.infrastructure.cache.redis_presence_store import RedisPresenceStore
from app.infrastructure.cache.redis_token_blacklist import RedisTokenBlacklist

from app.presentation.rest import (
    auth_controller, role_admin_controller, profile_controller,
    library_controller, presence_ws_controller,
)

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- DB schema ---
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_super_admin()

    # --- Singleton adapters ---
    event_publisher = KafkaEventPublisher()
    await event_publisher.start()
    app.state.event_publisher = event_publisher

    presence_store = RedisPresenceStore()
    app.state.presence_store = presence_store

    token_blacklist = RedisTokenBlacklist()
    app.state.token_blacklist = token_blacklist

    # --- Outbox dispatcher (Transactional Outbox -> Kafka relay) ---
    outbox_dispatcher = OutboxDispatcher(event_publisher)
    outbox_dispatcher.start()
    app.state.outbox_dispatcher = outbox_dispatcher

    # --- Kafka consumers ---
    abuse_consumer_logic = AbuseEventConsumer()
    consumers = [
        KafkaConsumerBase(settings.kafka_topic_gift_card_abuse, f"{settings.kafka_consumer_group}-abuse",
                           abuse_consumer_logic.handle),
        KafkaConsumerBase(settings.kafka_topic_user_events, f"{settings.kafka_consumer_group}-user-sync",
                           handle_user_registered),
        KafkaConsumerBase(settings.kafka_topic_ownership, f"{settings.kafka_consumer_group}-library",
                           handle_ownership_granted),
        KafkaConsumerBase(settings.kafka_topic_item_granted, f"{settings.kafka_consumer_group}-inventory",
                           handle_item_or_trade_event),
        KafkaConsumerBase(settings.kafka_topic_post_reacted, f"{settings.kafka_consumer_group}-top-posts",
                           handle_post_reacted),
    ]
    for consumer in consumers:
        await consumer.start()
    app.state.consumers = consumers

    logger.info("%s started successfully", settings.app_name)
    yield

    # --- Shutdown: reverse order ---
    for consumer in consumers:
        await consumer.stop()
    await outbox_dispatcher.stop()
    await event_publisher.stop()
    await presence_store.close()
    await token_blacklist.close()
    await engine.dispose()
    logger.info("%s shut down cleanly", settings.app_name)


app = FastAPI(
    title="Arcadia - Auth & Profile Service",
    description="Combined Auth + Profile bounded contexts, Clean Architecture, event-driven.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(CorrelationIdMiddleware)

register_exception_handlers(app)
configure_metrics(app)
configure_tracing(app)

# --- Rate limiting (slowapi) ---
app.state.limiter = auth_controller.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- Routers ---
app.include_router(auth_controller.router)
app.include_router(role_admin_controller.router)
app.include_router(profile_controller.router)
app.include_router(library_controller.router)
app.include_router(presence_ws_controller.router)


@app.get("/health", tags=["Health"], include_in_schema=False)
async def health():
    return {"status": "ok", "service": settings.app_name}
