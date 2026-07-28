import asyncio
import contextlib
import json
import logging
from datetime import UTC, datetime

from sqlalchemy import select, update

from app.config import settings
from app.infrastructure.db.models.outbox_model import OutboxModel
from app.infrastructure.db.session import db_session_scope
from app.infrastructure.messaging.kafka_producer import KafkaEventPublisher

logger = logging.getLogger(__name__)

# The platform's envelope version. Consumers refuse a message whose schema_version is absent or
# zero, which is what every event this service published used to be.
SCHEMA_VERSION = 1


def envelope_for(row: OutboxModel) -> dict:
    """Wrap an outbox row in the envelope the rest of the platform speaks.

    Every field comes off the row, which already carried all of them — the bug was never missing
    data, it was publishing the payload **flat** with `event_type` merged into it. The Go services
    validate the envelope before they look at anything else and reject a message with no
    `event_id`, `aggregate_id`, `occurred_at` or `schema_version`; the Python ones look for the
    payload under a `payload` key and find nothing. So every event this service emitted was
    unreadable by every consumer on the platform.

    `event_id` is the outbox row's own id rather than a fresh UUID. Consumers deduplicate on it,
    and the row id is the one value that stays the same across the retries that make an at-least-
    once outbox work — a new id per attempt would turn every retry into a new event.
    """
    return {
        "event_id": row.id,
        "event_type": row.event_type,
        "schema_version": SCHEMA_VERSION,
        "occurred_at": _rfc3339(row.created_at),
        "producer": settings.app_name,
        "aggregate_type": row.aggregate_type,
        "aggregate_id": row.aggregate_id,
        "payload": json.loads(row.payload),
    }


def _rfc3339(moment: datetime) -> str:
    """Go's `time.Time` will not parse a naive timestamp, and SQLite/Postgres round-trips can
    hand one back. Assume UTC rather than emit something the other half of the platform cannot
    read."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.isoformat()


class OutboxDispatcher:
    """
    Implements the Transactional Outbox pattern's "relay" half:
    polls rows where dispatched = false, publishes each to Kafka (topic taken from
    the row itself), and marks it dispatched. If Kafka publish fails, the row is
    left undispatched and retried on the next poll -> at-least-once delivery.
    Downstream consumers are expected to be idempotent (dedupe by event_id).
    """

    def __init__(self, event_publisher: KafkaEventPublisher):
        self._event_publisher = event_publisher
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "OutboxDispatcher started (poll_interval=%ss)", settings.outbox_poll_interval_seconds
        )

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            # Awaiting a cancelled task is how you wait for it to actually stop; the
            # CancelledError it raises is the confirmation, not a failure.
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        logger.info("OutboxDispatcher stopped")

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await self._dispatch_batch()
            except Exception:
                logger.exception("OutboxDispatcher batch failed; will retry next interval")
            await asyncio.sleep(settings.outbox_poll_interval_seconds)

    async def _dispatch_batch(self) -> None:
        async with db_session_scope() as session:
            result = await session.execute(
                select(OutboxModel)
                .where(OutboxModel.dispatched.is_(False))
                .order_by(OutboxModel.created_at)
                .limit(settings.outbox_batch_size)
            )
            rows = result.scalars().all()
            if not rows:
                return

            for row in rows:
                try:
                    await self._event_publisher.publish(
                        topic=row.topic,
                        key=row.aggregate_id,
                        payload=envelope_for(row),
                    )

                    await session.execute(
                        update(OutboxModel)
                        .where(OutboxModel.id == row.id)
                        .values(dispatched=True, dispatched_at=datetime.now(UTC))
                    )
                    await session.commit()
                except Exception:
                    logger.exception(
                        "Failed to dispatch outbox row id=%s (topic=%s) - left for retry",
                        row.id,
                        row.topic,
                    )
                    await session.rollback()
