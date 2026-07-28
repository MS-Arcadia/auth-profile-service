from app.domain.profile.exceptions import ProfileNotFoundError
from app.application.ports.profile_ports import ProfileRepositoryPort, PresenceStorePort


class GetProfileUseCase:

    def __init__(self, profile_repo: ProfileRepositoryPort, presence_store: PresenceStorePort):
        self._profile_repo = profile_repo
        self._presence_store = presence_store

    async def execute(self, user_id: str):
        profile = await self._profile_repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundError(user_id)

        # Presence is sourced live from Redis (real-time), overriding the DB-synced flag.
        profile.online = await self._presence_store.is_online(user_id)
        return profile
