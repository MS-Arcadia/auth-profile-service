"""Resolving what a person types into the account a gift is addressed to.

A gift is addressed by account id — a UUID — and nobody knows their friend's UUID. The
storefront asked for one anyway and sent whatever was typed, so a display name went through
as an id, nothing along the saga checked it, and the game landed on an account that did not
exist while the buyer was charged in full.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.application.use_cases.auth.find_recipient import FindRecipientUseCase
from app.domain.auth.enums import Role, UserState
from app.domain.auth.exceptions import RecipientNotFoundError, RecipientNotUniqueError
from app.domain.auth.user import User


def user(*, user_id: str, email: str, name: str, state: UserState = UserState.ACTIVE) -> User:
    return User(
        id=user_id,
        email=email,
        password_hash="x",
        display_name=name,
        role=Role.BASIC_USER,
        state=state,
        created_at=datetime.now(UTC),
    )


class FakeUsers:
    def __init__(self, *users: User) -> None:
        self._users = list(users)

    async def get_by_email(self, email: str):
        return next((u for u in self._users if u.email == email), None)

    async def find_active_by_display_name(self, display_name: str):
        wanted = display_name.strip().lower()
        return [u for u in self._users if u.display_name.lower() == wanted and u.state is UserState.ACTIVE]


NADIA = user(user_id="u-1", email="nadia@example.com", name="Nadia Farr")
SAM = user(user_id="u-2", email="sam@example.com", name="Sam Okafor")


@pytest.mark.asyncio
async def test_an_email_resolves_to_its_account():
    found = await FindRecipientUseCase(FakeUsers(NADIA, SAM)).execute("nadia@example.com")
    assert found.id == "u-1"


@pytest.mark.asyncio
async def test_an_email_is_matched_case_insensitively():
    """People capitalise their own address in ways their keyboard decided for them."""
    found = await FindRecipientUseCase(FakeUsers(NADIA)).execute("  Nadia@Example.com ")
    assert found.id == "u-1"


@pytest.mark.asyncio
async def test_a_display_name_resolves_when_it_is_unambiguous():
    found = await FindRecipientUseCase(FakeUsers(NADIA, SAM)).execute("nadia farr")
    assert found.id == "u-1"


@pytest.mark.asyncio
async def test_two_people_with_one_name_is_reported_not_guessed():
    """Picking the first is how a gift reaches a stranger who shares a name."""
    twin = user(user_id="u-3", email="other@example.com", name="Nadia Farr")

    with pytest.raises(RecipientNotUniqueError) as caught:
        await FindRecipientUseCase(FakeUsers(NADIA, twin)).execute("Nadia Farr")

    assert caught.value.count == 2
    # The message has to say what to do next, not only that something is wrong.
    assert "email" in str(caught.value)


@pytest.mark.asyncio
async def test_nobody_by_that_name_is_not_found():
    with pytest.raises(RecipientNotFoundError):
        await FindRecipientUseCase(FakeUsers(NADIA)).execute("Nobody At All")


@pytest.mark.asyncio
async def test_an_account_that_cannot_use_a_gift_does_not_resolve():
    """A gift to somebody pending approval or banned is charged for and never usable."""
    pending = user(user_id="u-4", email="new@example.com", name="New Person", state=UserState.PENDING)
    users = FakeUsers(pending)

    with pytest.raises(RecipientNotFoundError):
        await FindRecipientUseCase(users).execute("new@example.com")
    with pytest.raises(RecipientNotFoundError):
        await FindRecipientUseCase(users).execute("New Person")


@pytest.mark.asyncio
async def test_an_empty_query_finds_nobody_rather_than_everybody():
    with pytest.raises(RecipientNotFoundError):
        await FindRecipientUseCase(FakeUsers(NADIA)).execute("   ")


@pytest.mark.asyncio
async def test_a_partial_name_does_not_match():
    """Exact matches only. This answers "is this person here", and must not become a way to
    enumerate the platform's users."""
    with pytest.raises(RecipientNotFoundError):
        await FindRecipientUseCase(FakeUsers(NADIA)).execute("Nadia")
