from app.application.ports.auth_ports import UserRepositoryPort
from app.domain.auth.enums import Role, UserState
from app.domain.auth.exceptions import InvalidRoleTransitionError


class ListActiveUserIdsUseCase:
    """Backs the internal directory lookup other services use to reach "everyone".

    The first (and so far only) consumer is festival-service, which needs the full active
    user directory to populate a platform-wide `FestivalStarted.audience` when a festival
    goes live. Restricted to SUPPORT/ADMIN, same bar as the other `/admin/users/*` routes,
    since it is a bulk read of the user directory.
    """

    def __init__(self, user_repo: UserRepositoryPort):
        self._user_repo = user_repo

    async def execute(self, actor_role: Role, state: UserState = UserState.ACTIVE) -> list[str]:
        if actor_role not in (Role.SUPPORT, Role.ADMIN):
            raise InvalidRoleTransitionError("Only SUPPORT or ADMIN can list the user directory.")
        return await self._user_repo.list_ids_by_state(state)
