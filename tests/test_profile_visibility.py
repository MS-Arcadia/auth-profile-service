"""Who sees a hidden game.

A game hidden from a profile disappeared for everybody, its owner included — the controller
returned `visible_games()` to every caller. Since the only place to unhide one is the list it
had just vanished from, hiding a game was permanent: the unhide route and the domain method
behind it both existed and could not be reached.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.domain.profile.profile import Profile
from app.domain.profile.value_objects import OwnedGame


def owned(game_id: str, *, hidden: bool = False) -> OwnedGame:
    return OwnedGame(id=f"og-{game_id}", user_id="u-1", game_id=game_id, hidden=hidden)


def profile_with(*games: OwnedGame) -> Profile:
    return Profile(
        user_id="u-1",
        display_name="Nadia Farr",
        avatar_url="",
        online=False,
        owned_games=list(games),
        updated_at=datetime.now(UTC),
    )


def test_a_visitor_is_shown_only_what_the_owner_kept_visible():
    profile = profile_with(
        owned("g-1"),
        owned("g-2", hidden=True),
    )
    assert [g.game_id for g in profile.visible_games()] == ["g-1"]


def test_the_owner_still_has_every_game_to_offer_the_screen():
    """`owned_games` is what the controller hands an owner, and it must keep the hidden one
    — otherwise there is nothing to press unhide on."""
    profile = profile_with(
        owned("g-1"),
        owned("g-2", hidden=True),
    )
    assert [(g.game_id, g.hidden) for g in profile.owned_games] == [
        ("g-1", False),
        ("g-2", True),
    ]


def test_hiding_and_unhiding_are_reversible():
    profile = profile_with(owned("g-1"))

    profile.hide_game("g-1")
    assert profile.visible_games() == []

    profile.unhide_game("g-1")
    assert [g.game_id for g in profile.visible_games()] == ["g-1"]


def test_unhiding_something_that_was_never_hidden_changes_nothing():
    profile = profile_with(owned("g-1"))
    profile.unhide_game("g-1")
    assert [g.hidden for g in profile.owned_games] == [False]


def test_hiding_a_game_that_is_not_owned_is_ignored_rather_than_raising():
    profile = profile_with(owned("g-1"))
    profile.hide_game("not-owned")
    assert [g.hidden for g in profile.owned_games] == [False]
