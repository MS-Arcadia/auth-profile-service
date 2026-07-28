from app.application.ports.profile_ports import ProfileRepositoryPort


class UserSyncProjector:
    def __init__(self, profile_repo: ProfileRepositoryPort):
        self._profile_repo = profile_repo

    async def handle(self, event: dict) -> None:
        """event = {"user_id": ..., "display_name": ...}"""
        await self._profile_repo.create_if_missing(
            user_id=event["user_id"], display_name=event.get("display_name", "")
        )
