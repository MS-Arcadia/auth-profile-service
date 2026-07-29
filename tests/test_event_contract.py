"""The event contract with the rest of the platform.

Every failure this file covers was silent. An event published in the wrong shape is not an error
anywhere — the producer commits happily, the consumer rejects the envelope or finds no handler, and
nothing on either side says so. The only symptom is a wallet that never appears and a library that
never fills.

These are unit tests: no Kafka, no database. What they assert is the *shape* on the wire, which is
the part two services have to agree on.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from app.domain.auth import events as auth_events
from app.domain.profile import events as profile_events
from app.infrastructure.messaging.envelope import Envelope, MalformedEnvelope, route
from app.infrastructure.messaging.outbox_dispatcher import SCHEMA_VERSION, envelope_for

_FAKE_USER_ID = "bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb"
_FAKE_PAYLOAD = json.dumps({"user_id": _FAKE_USER_ID, "role": "BASIC_USER"})


@dataclass
class FakeRow:
    """An outbox row, with the columns the dispatcher reads."""

    id: str = "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa"
    aggregate_type: str = "User"
    aggregate_id: str = _FAKE_USER_ID
    event_type: str = "arcadia.auth.v1.UserRegistered"
    created_at: datetime = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
    payload: str = _FAKE_PAYLOAD


# --- what this service publishes ----------------------------------------


def test_events_carry_the_platforms_fully_qualified_name():
    """Consumers route on the whole string. A bare class name matches nothing, and the wallet has
    been waiting for this exact one since before this service existed."""
    event = auth_events.UserRegistered(user_id="u-1", role="BASIC_USER")
    assert event.event_type == "arcadia.auth.v1.UserRegistered"

    presence = profile_events.PresenceChanged(user_id="u-1", online=True)
    assert presence.event_type == "arcadia.profile.v1.PresenceChanged"


def test_the_payload_does_not_repeat_the_envelope_fields():
    """`event_id` and `occurred_at` belong to the envelope. Carrying them in both places is how a
    consumer ends up reading one while the producer sets the other."""
    payload = auth_events.UserRegistered(user_id="u-1").to_payload()
    assert "event_id" not in payload
    assert "occurred_at" not in payload
    assert payload["user_id"] == "u-1"


def test_the_published_message_is_a_platform_envelope():
    """The shape the Go services validate before they look at anything else. Missing any of these
    is a rejected message, which is what every event this service published used to be."""
    message = envelope_for(FakeRow())

    assert message["event_id"] == FakeRow.id
    assert message["event_type"] == "arcadia.auth.v1.UserRegistered"
    # Spelled out rather than chained: `x == SCHEMA_VERSION >= 1` reads like two assertions and is
    # one, and the version being positive is the half the Go validator actually enforces.
    assert message["schema_version"] == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 1
    assert message["aggregate_type"] == "User"
    assert message["aggregate_id"] == FakeRow.aggregate_id
    assert message["producer"]
    assert message["occurred_at"].startswith("2026-07-28T12:00:00")
    # Nested, not flattened. This is the whole bug in one assertion.
    assert message["payload"] == {"user_id": FakeRow.aggregate_id, "role": "BASIC_USER"}


def test_the_event_id_is_the_outbox_row_id():
    """Consumers deduplicate on `event_id`, and the outbox retries. A fresh UUID per attempt would
    turn every retry into a new event and undo the deduplication entirely."""
    row = FakeRow()
    assert envelope_for(row)["event_id"] == row.id
    assert envelope_for(row)["event_id"] == envelope_for(row)["event_id"]


def test_a_naive_timestamp_is_published_as_utc():
    """Go's time.Time will not parse a timestamp with no offset, and a database round-trip can hand
    one back."""
    row = FakeRow(created_at=datetime(2026, 7, 28, 12, 0))
    assert envelope_for(row)["occurred_at"].endswith("+00:00")


# --- what this service consumes -----------------------------------------


def test_a_platform_envelope_parses():
    envelope = Envelope.parse(envelope_for(FakeRow()))
    assert envelope.event_type == "arcadia.auth.v1.UserRegistered"
    assert envelope.payload["role"] == "BASIC_USER"


def test_a_flat_event_is_refused_with_a_message_that_says_why():
    """The shape this service used to publish. Refused rather than tolerated, because a flat event
    on one of these topics means a producer is broken and silence would hide it."""
    with pytest.raises(MalformedEnvelope, match="flat event"):
        Envelope.parse(
            {"event_id": "1", "event_type": "arcadia.auth.v1.UserRegistered", "user_id": "u-1"}
        )


def test_an_envelope_with_no_identity_is_refused():
    with pytest.raises(MalformedEnvelope):
        Envelope.parse({"payload": {"user_id": "u-1"}})


@pytest.mark.asyncio
async def test_an_unknown_event_type_is_ignored_not_failed():
    """These topics are shared. Subscribing to `wallet-events` for gift-card abuse also means
    receiving every debit and credit on the platform; treating those as failures would retry each
    one three times and bury the log in other services' healthy traffic.
    """
    message = envelope_for(FakeRow(event_type="arcadia.wallet.v1.WalletDebited"))
    assert route(message, {"arcadia.wallet.v1.GiftCardAbuseDetected": _unreachable}) is None


def test_a_known_event_type_finds_its_handler():
    message = envelope_for(FakeRow())
    routed = route(message, {"arcadia.auth.v1.UserRegistered": _unreachable})
    assert routed is not None
    envelope, handler = routed
    assert handler is _unreachable
    assert envelope.payload["role"] == "BASIC_USER"


async def _unreachable(_payload: dict) -> None:  # pragma: no cover - identity only
    raise AssertionError("this handler is only used as a marker")
