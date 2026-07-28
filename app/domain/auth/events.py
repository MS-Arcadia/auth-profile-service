from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import uuid


@dataclass(frozen=True)
class DomainEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def event_type(self) -> str:
        return self.__class__.__name__

    def to_payload(self) -> dict:
        data = asdict(self)
        return data


@dataclass(frozen=True)
class UserRegistered(DomainEvent):
    user_id: str = ""
    email: str = ""
    display_name: str = ""
    role: str = ""
    state: str = ""


@dataclass(frozen=True)
class RegistrationApproved(DomainEvent):
    user_id: str = ""
    decided_by: str = ""


@dataclass(frozen=True)
class RegistrationRejected(DomainEvent):
    user_id: str = ""
    decided_by: str = ""
    reason: str = ""


@dataclass(frozen=True)
class RoleRequested(DomainEvent):
    request_id: str = ""
    user_id: str = ""
    requested_role: str = ""


@dataclass(frozen=True)
class RoleGranted(DomainEvent):
    user_id: str = ""
    old_role: str = ""
    new_role: str = ""
    granted_by: str = ""


@dataclass(frozen=True)
class UserBanned(DomainEvent):
    user_id: str = ""
    banned_by: str = ""
    reason: str = ""


@dataclass(frozen=True)
class UserUnbanned(DomainEvent):
    user_id: str = ""
    unbanned_by: str = ""
