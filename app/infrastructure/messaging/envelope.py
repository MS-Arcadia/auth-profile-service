"""Reading the platform's event envelope.

Every service on this platform publishes the same wrapper — `event_id`, `event_type`,
`schema_version`, `occurred_at`, `producer`, `aggregate_type`, `aggregate_id`, `payload` — and the
domain fields live *inside* `payload`, never at the top level.

This service's consumers used to read the top level directly: `event.get("user_id")`. Against a
real platform message that is always `None`, so the gift-card abuse handler logged "missing
user_id" for every message it ever saw and the library projector raised `KeyError`. Both failures
looked like the other service's fault.

The other half of the same problem: topics here carry **many** event types. `wallet-events` is
every balance movement on the platform, `game-events` is every catalog change. A consumer that
processes whatever arrives will act on events that have nothing to do with it, so routing on
`event_type` is not a refinement — it is the difference between working and not.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


class MalformedEnvelope(ValueError):
    """The message is not a platform event. Raised rather than tolerated: a topic this service
    subscribes to should not contain anything else, and quietly skipping would hide a
    misconfigured topic name forever."""


@dataclass(frozen=True)
class Envelope:
    event_id: str
    event_type: str
    aggregate_id: str
    payload: dict[str, Any]
    producer: str = ""
    occurred_at: str = ""

    @staticmethod
    def parse(message: Any) -> Envelope:
        if not isinstance(message, dict):
            raise MalformedEnvelope(f"expected a JSON object, got {type(message).__name__}")

        event_id = str(message.get("event_id") or "")
        event_type = str(message.get("event_type") or "")
        if not event_id or not event_type:
            raise MalformedEnvelope(f"event_id and event_type are required; got {event_id!r} / {event_type!r}")

        payload = message.get("payload")
        if not isinstance(payload, dict):
            # The specific shape this service used to publish, and the specific reason nothing
            # could read it. Named explicitly so the message says what is wrong.
            raise MalformedEnvelope(f"{event_type} has no `payload` object — a flat event is not a platform event")

        return Envelope(
            event_id=event_id,
            event_type=event_type,
            aggregate_id=str(message.get("aggregate_id") or ""),
            payload=payload,
            producer=str(message.get("producer") or ""),
            occurred_at=str(message.get("occurred_at") or ""),
        )


def route(message: Any, handlers: dict[str, Any]) -> tuple[Envelope, Any] | None:
    """Parse a message and find its handler, or return None when it is not ours.

    An unrecognised `event_type` is **ignored, not an error**. These topics are shared: subscribing
    to `wallet-events` to hear about gift-card abuse means also receiving every debit, credit and
    hold on the platform. Treating those as failures would retry each one three times and fill the
    log with other services' healthy traffic.
    """
    envelope = Envelope.parse(message)
    handler = handlers.get(envelope.event_type)
    if handler is None:
        logger.debug(
            "ignoring an event this service does not consume",
            extra={"event_type": envelope.event_type, "producer": envelope.producer},
        )
        return None
    return envelope, handler
