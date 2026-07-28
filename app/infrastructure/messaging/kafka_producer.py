import json
import logging

from aiokafka import AIOKafkaProducer

from app.application.ports.event_publisher_port import EventPublisherPort
from app.config import settings

logger = logging.getLogger(__name__)


class KafkaEventPublisher(EventPublisherPort):
    """Thin async wrapper around aiokafka producer. Started/stopped with app lifespan."""

    def __init__(self):
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            enable_idempotence=True,  # avoid duplicate publishes on retry
            acks="all",
        )
        await self._producer.start()
        logger.info("Kafka producer started (bootstrap=%s)", settings.kafka_bootstrap_servers)

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()
            logger.info("Kafka producer stopped")

    async def publish(self, topic: str, key: str, payload: dict) -> None:
        if self._producer is None:
            raise RuntimeError("KafkaEventPublisher.start() was not called before publish()")
        await self._producer.send_and_wait(topic, value=payload, key=key)
