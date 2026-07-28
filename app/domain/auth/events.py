import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

# The platform's event namespace for this service. Every other service uses the same shape —
# `arcadia.<service>.v1.<Event>` — and consumers route on the whole string, so a bare class name
# matches nothing. The wallet, for one, has been waiting for `arcadia.auth.v1.UserRegistered`
# since before this service existed.
NAMESPACE = "arcadia.auth.v1"


@dataclass(frozen=True)
class DomainEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def event_type(self) -> str:
        """The fully qualified name other services route on.

        Derived from the class name rather than written out per event, because the two must never
        disagree and a hand-written copy is how one of them ends up with a typo that no compiler
        sees — only a consumer that silently stops receiving anything.
        """
        return f"{NAMESPACE}.{self.__class__.__name__}"

    def to_payload(self) -> dict:
        """The domain fields only.

        `event_id` and `occurred_at` are envelope concerns and are excluded: duplicating them
        inside the payload is how a consumer ends up reading one and a producer setting the other.
        """
        data = asdict(self)
        data.pop("event_id", None)
        data.pop("occurred_at", None)
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
