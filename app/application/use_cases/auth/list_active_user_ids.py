from app.application.ports.auth_ports import UserRepositoryPort
from app.domain.auth.enums import Role, UserState
from app.domain.auth.exceptions import InvalidRoleTransitionError


class ListActiveUserIdsUseCase:
    """Backs the internal directory lookup other services use to reach "everyone".

    festival-service uses it unfiltered, to populate a platform-wide
    `FestivalStarted.audience`. notification-service filters by role, because
    "a developer submitted a game" and "somebody asked for a role" are addressed to whoever
    can act on them rather than to everyone — without the filter it would have to fetch the
    whole directory and discard almost all of it.

    Restricted to SUPPORT/ADMIN, same bar as the other `/admin/users/*` routes, since it is
    a bulk read of the user directory.
    """

    def __init__(self, user_repo: UserRepositoryPort):
        self._user_repo = user_repo

    async def execute(
        self,
        actor_role: Role,
        state: UserState = UserState.ACTIVE,
        role: Role | None = None,
    ) -> list[str]:
        if actor_role not in (Role.SUPPORT, Role.ADMIN):
            raise InvalidRoleTransitionError("Only SUPPORT or ADMIN can list the user directory.")
        return await self._user_repo.list_ids_by_state(state, role)
