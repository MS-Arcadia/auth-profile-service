"""The profile already stored an avatar_url; nothing ever wrote one."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.application.use_cases.profile.set_avatar import SetAvatarUseCase
from app.domain.profile.exceptions import ProfileNotFoundError
from app.domain.profile.profile import Profile


class FakeProfiles:
    def __init__(self, *profiles: Profile) -> None:
        self._profiles = {p.user_id: p for p in profiles}
        self.saved: list[Profile] = []

    async def get_by_user_id(self, user_id: str):
        return self._profiles.get(user_id)

    async def save(self, profile: Profile) -> None:
        self._profiles[profile.user_id] = profile
        self.saved.append(profile)


def _profile() -> Profile:
    return Profile(
        user_id="u-1",
        display_name="Nadia Farr",
        avatar_url="",
        updated_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_the_owner_can_set_an_avatar_url():
    repo = FakeProfiles(_profile())
    await SetAvatarUseCase(repo).execute("u-1", "https://cdn.example/me.png")

    assert repo._profiles["u-1"].avatar_url == "https://cdn.example/me.png"
    assert repo.saved


@pytest.mark.asyncio
async def test_a_missing_profile_is_not_created_by_setting_an_avatar():
    repo = FakeProfiles()
    with pytest.raises(ProfileNotFoundError):
        await SetAvatarUseCase(repo).execute("nobody", "https://cdn.example/me.png")
    assert repo.saved == []
