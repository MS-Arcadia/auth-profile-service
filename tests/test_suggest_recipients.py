"""Suggestions as a gift sender types, without turning lookup into a search.

Lookup stays exact: it answers "is this specific person here". Suggest is the
autocomplete — prefix on email or display name, a handful of active accounts,
never the caller. Typing `player@arcadia.exampl` has to surface the rest of the
address rather than wait for the last letter.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.application.use_cases.auth.suggest_recipients import SuggestRecipientsUseCase
from app.domain.auth.enums import Role, UserState
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

    async def search_active(self, query: str, *, limit: int, exclude_user_id: str = "") -> list[User]:
        needle = query.strip().lower()
        hits = [
            u
            for u in self._users
            if u.state is UserState.ACTIVE and u.id != exclude_user_id and _prefix_match(u, needle)
        ]
        return hits[:limit]


def _prefix_match(account: User, needle: str) -> bool:
    email = account.email.lower()
    name = account.display_name.lower()
    return email.startswith(needle) or name.startswith(needle) or f" {needle}" in f" {name}"


PLAYER = user(user_id="u-player", email="player@arcadia.example", name="Sam Player")
NADIA = user(user_id="u-1", email="nadia@example.com", name="Nadia Farr")
SAM = user(user_id="u-2", email="sam@example.com", name="Sam Okafor")


@pytest.mark.asyncio
async def test_an_unfinished_email_still_suggests_the_account():
    """The gift box used to 404 until the last character of the address was typed."""
    found = await SuggestRecipientsUseCase(FakeUsers(PLAYER, NADIA)).execute("player@arcadia.exampl")
    assert [u.id for u in found] == ["u-player"]


@pytest.mark.asyncio
async def test_a_name_prefix_suggests_matching_people():
    found = await SuggestRecipientsUseCase(FakeUsers(NADIA, SAM)).execute("Nad")
    assert [u.id for u in found] == ["u-1"]


@pytest.mark.asyncio
async def test_a_last_name_prefix_suggests_the_person():
    found = await SuggestRecipientsUseCase(FakeUsers(NADIA, SAM)).execute("Farr")
    assert [u.id for u in found] == ["u-1"]


@pytest.mark.asyncio
async def test_inactive_accounts_are_not_suggested():
    pending = user(user_id="u-4", email="new@example.com", name="New Person", state=UserState.PENDING)
    found = await SuggestRecipientsUseCase(FakeUsers(pending, NADIA)).execute("new@")
    assert found == []


@pytest.mark.asyncio
async def test_the_caller_is_not_suggested_to_themselves():
    found = await SuggestRecipientsUseCase(FakeUsers(NADIA, SAM)).execute("nadia", exclude_user_id="u-1")
    assert found == []


@pytest.mark.asyncio
async def test_a_short_query_suggests_nobody():
    """One character is too little to type and too much of a directory."""
    found = await SuggestRecipientsUseCase(FakeUsers(NADIA)).execute("n")
    assert found == []


@pytest.mark.asyncio
async def test_results_are_capped():
    crowd = [user(user_id=f"u-{i}", email=f"player{i}@arcadia.example", name=f"Player {i}") for i in range(20)]
    found = await SuggestRecipientsUseCase(FakeUsers(*crowd)).execute("player")
    assert len(found) == 8


@pytest.mark.asyncio
async def test_a_mid_word_fragment_is_not_a_match():
    """Contains-search would turn two letters in the middle of a name into a directory."""
    found = await SuggestRecipientsUseCase(FakeUsers(NADIA)).execute("dia")
    assert found == []


@pytest.mark.asyncio
async def test_a_percent_is_not_a_wildcard():
    """LIKE metacharacters in what was typed must not list everybody."""
    found = await SuggestRecipientsUseCase(FakeUsers(NADIA, SAM)).execute("%%")
    assert found == []
