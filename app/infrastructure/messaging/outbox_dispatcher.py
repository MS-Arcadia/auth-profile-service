import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.config import settings
from app.infrastructure.db.session import db_session_scope
from app.infrastructure.db.models.outbox_model import OutboxModel
from app.infrastructure.messaging.kafka_producer import KafkaEventPublisher

logger = logging.getLogger(__name__)


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
        logger.info("OutboxDispatcher started (poll_interval=%ss)", settings.outbox_poll_interval_seconds)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
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
                    import json
                    payload = json.loads(row.payload)
                    payload["event_type"] = row.event_type
                    await self._event_publisher.publish(topic=row.topic, key=row.aggregate_id, payload=payload)

                    await session.execute(
                        update(OutboxModel)
                        .where(OutboxModel.id == row.id)
                        .values(dispatched=True, dispatched_at=datetime.now(timezone.utc))
                    )
                    await session.commit()
                except Exception:
                    logger.exception("Failed to dispatch outbox row id=%s (topic=%s) - left for retry",
                                      row.id, row.topic)
                    await session.rollback()
