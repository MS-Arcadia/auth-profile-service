import pytest

from app.domain.auth.enums import Role, UserState
from app.domain.auth.exceptions import InvalidStateTransitionError
from app.domain.auth.user import User


def pending_user() -> User:
    """A leftover PENDING account — registration no longer produces these."""
    return User(
        id="u-pending",
        email="a@b.com",
        password_hash="h",
        display_name="A",
        role=Role.BASIC_USER,
        state=UserState.PENDING,
    )


def test_register_starts_active_with_basic_role():
    user = User.register(email="Test@Example.com", password_hash="hash", display_name="Test")
    assert user.state == UserState.ACTIVE
    assert user.can_login()
    assert user.role == Role.BASIC_USER
    assert user.email == "test@example.com"  # normalized
    events = user.pull_events()
    assert len(events) == 1
    # The fully qualified name, which is what other services route on. It was the bare class
    # name, and the wallet has been waiting for this exact string since before this service
    # existed — a name it never matched.
    assert events[0].event_type == "arcadia.auth.v1.UserRegistered"
    assert events[0].state == "ACTIVE"


def test_approve_registration_moves_pending_to_active():
    user = pending_user()
    user.approve_registration(decided_by="support-1")
    assert user.state == UserState.ACTIVE


def test_cannot_approve_twice():
    user = pending_user()
    user.approve_registration(decided_by="support-1")
    with pytest.raises(InvalidStateTransitionError):
        user.approve_registration(decided_by="support-1")


def test_cannot_approve_an_already_active_account():
    user = User.register(email="a@b.com", password_hash="h", display_name="A")
    with pytest.raises(InvalidStateTransitionError):
        user.approve_registration(decided_by="support-1")


def test_ban_requires_active_state():
    user = pending_user()
    with pytest.raises(InvalidStateTransitionError):
        user.ban(banned_by="support-1")


def test_ban_then_unban_cycle():
    user = User.register(email="a@b.com", password_hash="h", display_name="A")
    user.ban(banned_by="support-1", reason="abuse")
    assert user.state == UserState.BANNED
    user.unban(unbanned_by="support-1")
    assert user.state == UserState.ACTIVE


def test_change_role_preserves_single_role_invariant():
    user = User.register(email="a@b.com", password_hash="h", display_name="A")
    user.change_role(Role.DEVELOPER, granted_by="admin-1")
    assert user.role == Role.DEVELOPER  # exactly one role, always
