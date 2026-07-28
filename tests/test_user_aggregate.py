import pytest

from app.domain.auth.user import User
from app.domain.auth.enums import Role, UserState
from app.domain.auth.exceptions import InvalidStateTransitionError


def test_register_starts_pending_with_basic_role():
    user = User.register(email="Test@Example.com", password_hash="hash", display_name="Test")
    assert user.state == UserState.PENDING
    assert user.role == Role.BASIC_USER
    assert user.email == "test@example.com"  # normalized
    events = user.pull_events()
    assert len(events) == 1
    assert events[0].event_type == "UserRegistered"


def test_approve_registration_moves_pending_to_active():
    user = User.register(email="a@b.com", password_hash="h", display_name="A")
    user.pull_events()
    user.approve_registration(decided_by="support-1")
    assert user.state == UserState.ACTIVE


def test_cannot_approve_twice():
    user = User.register(email="a@b.com", password_hash="h", display_name="A")
    user.approve_registration(decided_by="support-1")
    with pytest.raises(InvalidStateTransitionError):
        user.approve_registration(decided_by="support-1")


def test_ban_requires_active_state():
    user = User.register(email="a@b.com", password_hash="h", display_name="A")
    with pytest.raises(InvalidStateTransitionError):
        user.ban(banned_by="support-1")  # still PENDING


def test_ban_then_unban_cycle():
    user = User.register(email="a@b.com", password_hash="h", display_name="A")
    user.approve_registration(decided_by="support-1")
    user.ban(banned_by="support-1", reason="abuse")
    assert user.state == UserState.BANNED
    user.unban(unbanned_by="support-1")
    assert user.state == UserState.ACTIVE


def test_change_role_preserves_single_role_invariant():
    user = User.register(email="a@b.com", password_hash="h", display_name="A")
    user.change_role(Role.DEVELOPER, granted_by="admin-1")
    assert user.role == Role.DEVELOPER  # exactly one role, always
