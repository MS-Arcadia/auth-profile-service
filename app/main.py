import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import CorrelationIdMiddleware
from app.infrastructure.cache.redis_presence_store import RedisPresenceStore
from app.infrastructure.cache.redis_token_blacklist import RedisTokenBlacklist
from app.infrastructure.db.base import Base
from app.infrastructure.db.bootstrap import seed_super_admin

# Imported for their side effect, not for their names: importing a model module is what registers
# its table on `Base.metadata`, and `create_all` below only creates what is registered. Without
# these five lines the metadata holds **zero** tables and the service starts against an empty
# schema. `ruff --fix` will happily delete them as unused, so they are marked.
from app.infrastructure.db.models import (  # noqa: F401
    login_audit_model,
    outbox_model,
    profile_models,
    role_request_model,
    user_model,
)
from app.infrastructure.db.session import engine
from app.infrastructure.messaging.consumers.abuse_event_consumer import AbuseEventConsumer
from app.infrastructure.messaging.consumers.profile_event_consumers import (
    handle_community_events,
    handle_game_events,
    handle_marketplace_events,
    handle_user_events,
)
from app.infrastructure.messaging.kafka_consumer_base import KafkaConsumerBase
from app.infrastructure.messaging.kafka_producer import KafkaEventPublisher
from app.infrastructure.messaging.outbox_dispatcher import OutboxDispatcher
from app.infrastructure.messaging.topics import ensure_topics
from app.infrastructure.observability.logging_config import configure_logging
from app.infrastructure.observability.metrics import configure_metrics
from app.infrastructure.observability.tracing import configure_tracing
from app.presentation.rest import (
    auth_controller,
    library_controller,
    presence_ws_controller,
    profile_controller,
    role_admin_controller,
)

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- DB schema ---
    #
    # Behind a switch, like RUN_MIGRATIONS on the other services. With it off the service still
    # starts, serves /livez and reports /readyz 503 — which is what makes a bad rollout visible
    # instead of a crash loop, and what CI asserts by starting the image with no database at all.
    if settings.run_migrations:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await seed_super_admin()
    else:
        logger.warning("RUN_MIGRATIONS is off: the schema is assumed to exist already")

    # --- Singleton adapters ---
    event_publisher = KafkaEventPublisher()
    if settings.kafka_enabled:
        await event_publisher.start()
    else:
        logger.warning("kafka is disabled: events will accumulate in the outbox unpublished")
    app.state.event_publisher = event_publisher

    presence_store = RedisPresenceStore()
    app.state.presence_store = presence_store

    token_blacklist = RedisTokenBlacklist()
    app.state.token_blacklist = token_blacklist

    # --- Outbox dispatcher (Transactional Outbox -> Kafka relay) ---
    outbox_dispatcher = OutboxDispatcher(event_publisher)
    if settings.kafka_enabled:
        outbox_dispatcher.start()
    app.state.outbox_dispatcher = outbox_dispatcher

    # Before any consumer subscribes. Auto-creation is off on this platform, and a consumer on a
    # topic that does not exist logs a metadata error on every refresh — about ten lines a second,
    # each, which on first boot buried everything real.
    if settings.kafka_enabled:
        await ensure_topics()

    # --- Kafka consumers ---
    # One consumer per topic, each with its own group so a slow projection cannot hold up an
    # unrelated one. Every handler routes on event_type internally, because these topics are
    # shared: subscribing to wallet-events to hear about gift-card abuse also means receiving every
    # debit, credit and hold on the platform.
    abuse_consumer_logic = AbuseEventConsumer()
    consumers = [
        KafkaConsumerBase(
            settings.kafka_topic_wallet_events,
            f"{settings.kafka_consumer_group}-abuse",
            abuse_consumer_logic.handle,
        ),
        KafkaConsumerBase(
            settings.kafka_topic_user_events,
            f"{settings.kafka_consumer_group}-user-sync",
            handle_user_events,
        ),
        KafkaConsumerBase(
            settings.kafka_topic_game_events,
            f"{settings.kafka_consumer_group}-library",
            handle_game_events,
        ),
        KafkaConsumerBase(
            settings.kafka_topic_trade_events,
            f"{settings.kafka_consumer_group}-inventory",
            handle_marketplace_events,
        ),
        KafkaConsumerBase(
            settings.kafka_topic_community_events,
            f"{settings.kafka_consumer_group}-top-posts",
            handle_community_events,
        ),
    ]
    if settings.kafka_enabled:
        for consumer in consumers:
            await consumer.start()
    app.state.consumers = consumers

    logger.info("%s started successfully", settings.app_name)
    yield

    # --- Shutdown: reverse order ---
    if settings.kafka_enabled:
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
#
# Everything under /v1, like every other service on the platform. This service mounted at /auth
# and /profile, which works on its own and does not once a gateway routes by path prefix or a
# client is generated from more than one of these OpenAPI documents.
#
# The WebSocket is mounted without the prefix as well as with it: a browser that already holds a
# /ws/presence URL keeps working, and there is no version negotiation to do on a socket that
# carries one message shape.
API_PREFIX = "/v1"

app.include_router(auth_controller.router, prefix=API_PREFIX)
app.include_router(role_admin_controller.router, prefix=API_PREFIX)
app.include_router(profile_controller.router, prefix=API_PREFIX)
app.include_router(library_controller.router, prefix=API_PREFIX)
app.include_router(presence_ws_controller.router, prefix=API_PREFIX)
app.include_router(presence_ws_controller.router)


# --- Health, the platform's way -----------------------------------------
#
# /livez and /readyz, not one /health. Liveness deliberately checks nothing; readiness checks
# dependencies. Conflating them is how a brief database blip restarts every replica and turns a
# short outage into a long one — which is why every other service here splits them, and why the
# compose healthcheck probes readiness specifically.


@app.get("/livez", tags=["Health"], include_in_schema=False)
async def livez() -> dict[str, str]:
    """The process is up. Nothing else is asserted, on purpose."""
    return {"status": "UP"}


@app.get("/readyz", tags=["Health"], include_in_schema=False)
async def readyz() -> JSONResponse:
    """Can this service actually serve a request?

    Postgres is critical: with no user table there is no authentication, so a replica that cannot
    reach it should leave the load balancer.

    Redis is **not** critical. It holds presence and the token blacklist. Losing it degrades both —
    presence goes stale, a logged-out token stays valid until it expires — and neither is worth
    refusing every login over. Saying so here, rather than discovering it during an incident, is
    the point of the distinction.
    """
    checks: dict[str, dict[str, str]] = {}
    healthy = True

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        checks["postgres"] = {"status": "UP"}
    except Exception as exc:
        checks["postgres"] = {"status": "DOWN", "error": str(exc)[:200]}
        healthy = False

    try:
        await app.state.presence_store.ping()
        checks["redis"] = {"status": "UP"}
    except Exception as exc:
        checks["redis"] = {"status": "DEGRADED", "error": str(exc)[:200]}

    report = {
        "status": "UP" if healthy else "DOWN",
        "service": settings.app_name,
        "checks": checks,
    }
    return JSONResponse(status_code=200 if healthy else 503, content=report)


@app.get("/health", tags=["Health"], include_in_schema=False)
async def health() -> dict[str, str]:
    """Kept as an alias so anything already pointing here does not break."""
    return {"status": "ok", "service": settings.app_name}
