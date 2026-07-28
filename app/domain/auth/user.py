from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List
import uuid

from app.domain.auth.enums import Role, UserState
from app.domain.auth.exceptions import InvalidStateTransitionError
from app.domain.auth import events as ev


@dataclass
class User:
    id: str
    email: str
    password_hash: str
    display_name: str
    role: Role
    state: UserState
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    _pending_events: List[ev.DomainEvent] = field(default_factory=list, repr=False, compare=False)

    @staticmethod
    def register(email: str, password_hash: str, display_name: str) -> "User":
        user = User(
            id=str(uuid.uuid4()),
            email=email.lower().strip(),
            password_hash=password_hash,
            display_name=display_name,
            role=Role.BASIC_USER,
            state=UserState.ACTIVE,
        )
        user._raise(ev.UserRegistered(
            user_id=user.id, email=user.email, display_name=user.display_name,
            role=user.role.value, state=user.state.value,
        ))
        return user

    def approve_registration(self, decided_by: str) -> None:
        if self.state != UserState.PENDING:
            raise InvalidStateTransitionError(self.state.value, "approve_registration")
        self.state = UserState.ACTIVE
        self._raise(ev.RegistrationApproved(user_id=self.id, decided_by=decided_by))

    def reject_registration(self, decided_by: str, reason: str = "") -> None:
        if self.state != UserState.PENDING:
            raise InvalidStateTransitionError(self.state.value, "reject_registration")
        self.state = UserState.REJECTED
        self._raise(ev.RegistrationRejected(user_id=self.id, decided_by=decided_by, reason=reason))

    def ban(self, banned_by: str, reason: str = "") -> None:
        if self.state != UserState.ACTIVE:
            raise InvalidStateTransitionError(self.state.value, "ban")
        self.state = UserState.BANNED
        self._raise(ev.UserBanned(user_id=self.id, banned_by=banned_by, reason=reason))

    def unban(self, unbanned_by: str) -> None:
        if self.state != UserState.BANNED:
            raise InvalidStateTransitionError(self.state.value, "unban")
        self.state = UserState.ACTIVE
        self._raise(ev.UserUnbanned(user_id=self.id, unbanned_by=unbanned_by))

    def change_role(self, new_role: Role, granted_by: str) -> None:
        """Replaces the single role value -> invariant 'exactly one role' trivially preserved."""
        old_role = self.role
        self.role = new_role
        self._raise(ev.RoleGranted(
            user_id=self.id, old_role=old_role.value, new_role=new_role.value, granted_by=granted_by,
        ))

    def can_login(self) -> bool:
        return self.state == UserState.ACTIVE

    def verify_password(self, plain_password: str, password_hasher) -> bool:
        return password_hasher.verify(plain_password, self.password_hash)

    def _raise(self, event: ev.DomainEvent) -> None:
        self._pending_events.append(event)

    def pull_events(self) -> List[ev.DomainEvent]:
        events, self._pending_events = self._pending_events, []
        return events
