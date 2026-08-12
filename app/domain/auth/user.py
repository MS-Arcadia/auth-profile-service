from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.domain.auth import events as ev
from app.domain.auth.enums import Role, UserState
from app.domain.auth.exceptions import InvalidStateTransitionError


@dataclass
class User:
    id: str
    email: str
    password_hash: str
    display_name: str
    role: Role
    state: UserState
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    _pending_events: list[ev.DomainEvent] = field(default_factory=list, repr=False, compare=False)

    @staticmethod
    def register(email: str, password_hash: str, display_name: str) -> User:
        user = User(
            id=str(uuid.uuid4()),
            email=email.lower().strip(),
            password_hash=password_hash,
            display_name=display_name,
            role=Role.BASIC_USER,
            # PENDING, not ACTIVE. Requirement 1.1 puts a new account in front of Support before
            # it can be used, and the state machine it specifies starts there:
            # PENDING → ACTIVE | REJECTED, then ACTIVE ↔ BANNED.
            #
            # This said ACTIVE, which made the whole approve/reject flow unreachable — nobody can
            # be approved when everybody is already active — and failed five of this service's own
            # tests, which had it right.
            state=UserState.PENDING,
        )
        user._raise(
            ev.UserRegistered(
                user_id=user.id,
                email=user.email,
                display_name=user.display_name,
                role=user.role.value,
                state=user.state.value,
            )
        )
        return user

    @staticmethod
    def register_super_admin(email: str, password_hash: str, display_name: str) -> User:
        """The initial administrator from requirement 1.1, active immediately.

        Its own factory rather than `register()` followed by assigning the fields, which is what
        the seed used to do. That worked for the row and lied in the event: `UserRegistered` had
        already been built with PENDING and BASIC_USER, so every consumer — the wallet among them
        — learned that the platform's administrator was an ordinary user awaiting approval.

        There is nobody to approve the first administrator, which is exactly why this bypasses the
        state machine instead of pretending to go through it.
        """
        user = User(
            id=str(uuid.uuid4()),
            email=email.lower().strip(),
            password_hash=password_hash,
            display_name=display_name,
            role=Role.ADMIN,
            state=UserState.ACTIVE,
        )
        user._raise(
            ev.UserRegistered(
                user_id=user.id,
                email=user.email,
                display_name=user.display_name,
                role=user.role.value,
                state=user.state.value,
            )
        )
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
        self._raise(
            ev.RoleGranted(
                user_id=self.id,
                old_role=old_role.value,
                new_role=new_role.value,
                granted_by=granted_by,
            )
        )

    def can_login(self) -> bool:
        return self.state == UserState.ACTIVE

    def verify_password(self, plain_password: str, password_hasher) -> bool:
        return password_hasher.verify(plain_password, self.password_hash)

    def _raise(self, event: ev.DomainEvent) -> None:
        self._pending_events.append(event)

    def pull_events(self) -> list[ev.DomainEvent]:
        events, self._pending_events = self._pending_events, []
        return events
