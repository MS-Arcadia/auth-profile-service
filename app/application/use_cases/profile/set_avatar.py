from app.application.ports.profile_ports import ProfileRepositoryPort
from app.domain.profile.exceptions import ProfileNotFoundError


class SetAvatarUseCase:
    def __init__(self, profile_repo: ProfileRepositoryPort):
        self._profile_repo = profile_repo

    async def execute(self, user_id: str, avatar_url: str) -> None:
        profile = await self._profile_repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundError(user_id)
        profile.set_avatar(avatar_url)
        await self._profile_repo.save(profile)
