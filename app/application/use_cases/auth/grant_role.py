from app.domain.auth.enums import Role
from app.domain.auth.exceptions import UserNotFoundError
from app.domain.auth.role_policy import RolePolicy
from app.application.ports.auth_ports import UserRepositoryPort


class GrantRoleUseCase:

    def __init__(self, user_repo: UserRepositoryPort):
        self._user_repo = user_repo

    async def execute(self, actor_role: Role, target_user_id: str, new_role: Role, granted_by: str) -> None:
        RolePolicy.assert_can_grant(actor_role, new_role)

        user = await self._user_repo.get_by_id(target_user_id)
        if user is None:
            raise UserNotFoundError(target_user_id)

        user.change_role(new_role, granted_by)

        events = user.pull_events()
        await self._user_repo.save(user, events)
