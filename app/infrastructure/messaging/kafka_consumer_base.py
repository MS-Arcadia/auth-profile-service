import asyncio
import contextlib
import json
import logging
from collections.abc import Awaitable, Callable

from aiokafka import AIOKafkaConsumer

from app.config import settings

logger = logging.getLogger(__name__)

Handler = Callable[[dict], Awaitable[None]]


class KafkaConsumerBase:
    """
    Generic consumer runner. Each concrete consumer wires a topic + an async handler.
    On handler failure, the message is logged and skipped after `max_retries` local
    retries (simulating a DLQ hand-off point) instead of crashing the whole service
    -> Bulkhead-style isolation between consumers.
    """

    def __init__(self, topic: str, group_id: str, handler: Handler, max_retries: int = 3):
        self._topic = topic
        self._group_id = group_id
        self._handler = handler
        self._max_retries = max_retries
        self._consumer: AIOKafkaConsumer | None = None
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        self._consumer = AIOKafkaConsumer(
            self._topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=self._group_id,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            enable_auto_commit=False,  # manual commit AFTER successful handling -> at-least-once
            auto_offset_reset="earliest",
        )
        await self._consumer.start()
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Kafka consumer started for topic=%s group=%s", self._topic, self._group_id)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            # Awaiting a cancelled task is how you wait for it to actually stop; the
            # CancelledError it raises is the confirmation, not a failure.
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self._consumer:
            await self._consumer.stop()
        logger.info("Kafka consumer stopped for topic=%s", self._topic)

    async def _run_loop(self) -> None:
        assert self._consumer is not None
        async for message in self._consumer:
            if not self._running:
                break
            await self._handle_with_retry(message.value)
            await self._consumer.commit()

    async def _handle_with_retry(self, payload: dict) -> None:
        for attempt in range(1, self._max_retries + 1):
            try:
                await self._handler(payload)
                return
            except Exception:
                logger.exception(
                    "Handler failed for topic=%s attempt=%s/%s payload=%s",
                    self._topic,
                    attempt,
                    self._max_retries,
                    payload,
                )
                if attempt == self._max_retries:
                    logger.error(
                        "Giving up on message for topic=%s after %s attempts; " "would route to DLQ in production (%s)",
                        self._topic,
                        self._max_retries,
                        payload,
                    )
                else:
                    await asyncio.sleep(0.5 * attempt)
