from app.application.ports.auth_ports import UserRepositoryPort
from app.domain.auth.enums import Role
from app.domain.auth.exceptions import UserNotFoundError
from app.domain.auth.role_policy import RolePolicy


class BanUserUseCase:
    def __init__(self, user_repo: UserRepositoryPort):
        self._user_repo = user_repo

    async def execute(
        self, actor_role: Role, target_user_id: str, ban: bool, actor_id: str, reason: str = ""
    ) -> None:
        RolePolicy.assert_can_ban(actor_role)

        user = await self._user_repo.get_by_id(target_user_id)
        if user is None:
            raise UserNotFoundError(target_user_id)

        if ban:
            user.ban(actor_id, reason)
        else:
            user.unban(actor_id)

        events = user.pull_events()
        await self._user_repo.save(user, events)
