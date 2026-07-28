from app.application.ports.profile_ports import ProfileRepositoryPort


class HideGameUseCase:

    def __init__(self, profile_repo: ProfileRepositoryPort):
        self._profile_repo = profile_repo

    async def execute(self, user_id: str, game_id: str, hidden: bool) -> None:
        await self._profile_repo.set_hidden(user_id, game_id, hidden)
