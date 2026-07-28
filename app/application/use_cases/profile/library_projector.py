import uuid
from app.application.ports.profile_ports import ProfileRepositoryPort
from app.domain.profile.value_objects import OwnedGame


class LibraryProjector:

    def __init__(self, profile_repo: ProfileRepositoryPort):
        self._profile_repo = profile_repo

    async def handle(self, event: dict) -> None:
        """event = {"user_id": ..., "game_id": ...}"""
        user_id = event["user_id"]
        await self._profile_repo.create_if_missing(user_id, display_name=event.get("display_name", ""))

        owned_game = OwnedGame(
            id=str(uuid.uuid4()),
            user_id=user_id,
            game_id=event["game_id"],
        )
        await self._profile_repo.add_owned_game(owned_game)
