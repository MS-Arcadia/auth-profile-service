import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

# Profile's own namespace. Auth and Profile share a deployment but are separate contexts, and
# their events should say so — something subscribing to presence has no business receiving
# account state changes.
NAMESPACE = "arcadia.profile.v1"


@dataclass(frozen=True)
class DomainEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def event_type(self) -> str:
        """The fully qualified name other services route on. See `domain/auth/events.py`."""
        return f"{NAMESPACE}.{self.__class__.__name__}"

    def to_payload(self) -> dict:
        """The domain fields only — `event_id` and `occurred_at` belong to the envelope."""
        data = asdict(self)
        data.pop("event_id", None)
        data.pop("occurred_at", None)
        return data


@dataclass(frozen=True)
class PresenceChanged(DomainEvent):
    user_id: str = ""
    online: bool = False
