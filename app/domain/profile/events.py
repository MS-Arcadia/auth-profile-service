from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


@dataclass(frozen=True)
class DomainEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def event_type(self) -> str:
        return self.__class__.__name__


@dataclass(frozen=True)
class PresenceChanged(DomainEvent):
    user_id: str = ""
    online: bool = False
