"""Creating the Kafka topics this service needs.

Broker-side auto-creation is off on this platform, deliberately: with it on, a typo in a topic name
silently creates a topic nobody produces to, and the bug surfaces much later as a consumer that
never receives anything.

The consequence is that a topic has to be created by somebody, and until it exists aiokafka logs
`Topic X not found in cluster metadata` on every metadata refresh — roughly ten lines a second, per
consumer. On first boot this service produced about twenty error lines a second for topics that
were simply not there yet, which is worse than useless: it buries anything real.

So two categories are created here:

* the topics this service **produces** to (`user-events`, `presence-events`), which are its own
  responsibility in the same way every other service creates its own;
* the topics it **consumes** from services that do not exist yet — Marketplace and Community. An
  empty topic is free, a consumer group on one is silent, and the alternative is either that log
  flood or not subscribing at all and having to remember to come back.

Topics owned by services that *do* exist — `wallet-events`, `game-events` — are deliberately absent.
Those services create them, and creating them from here would mean this service defining the
partition count for somebody else's stream.
"""

from __future__ import annotations

import contextlib
import logging

from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from aiokafka.errors import TopicAlreadyExistsError

from app.config import settings

logger = logging.getLogger(__name__)

# One partition, matching the rest of the platform's local topology. Ordering per aggregate is what
# matters here and the key is the aggregate id, so more partitions would buy throughput this stack
# has no use for while making per-user ordering depend on the partitioner.
PARTITIONS = 1
REPLICATION = 1


def topics_to_create() -> list[str]:
    return [
        settings.kafka_topic_user_events,
        settings.kafka_topic_presence_events,
        settings.kafka_topic_trade_events,
        settings.kafka_topic_community_events,
    ]


async def ensure_topics() -> None:
    """Create what is missing, tolerate what is there.

    Failure is logged and swallowed rather than fatal. A broker that is briefly unreachable at boot
    must not stop this service from serving logins — authentication does not need Kafka, and the
    consumers retry on their own.
    """
    admin = AIOKafkaAdminClient(bootstrap_servers=settings.kafka_bootstrap_servers)
    try:
        await admin.start()
    except Exception:
        logger.exception("could not reach Kafka to create topics; consumers will retry")
        return

    try:
        wanted = [
            NewTopic(name=name, num_partitions=PARTITIONS, replication_factor=REPLICATION)
            for name in topics_to_create()
        ]
        with contextlib.suppress(TopicAlreadyExistsError):
            await admin.create_topics(wanted)
        logger.info("kafka topics ready", extra={"topics": ",".join(topics_to_create())})
    except Exception:
        logger.exception("could not create Kafka topics; consumers will retry")
    finally:
        with contextlib.suppress(Exception):
            await admin.close()
