from app.application.ports.auth_ports import UserRepositoryPort
from app.domain.auth.enums import Role, UserState
from app.domain.auth.exceptions import InvalidRoleTransitionError
from app.domain.auth.user import User


class ListUsersUseCase:
    """The admin screen's directory: everyone, with enough of each account to act on it.

    Distinct from `ListActiveUserIdsUseCase`, which answers "who is everybody" for a
    platform-wide broadcast and returns bare ids. This one is read by a person deciding
    whether to grant a role or ban somebody, so it carries the name, the email, the role and
    the state — none of which an id list can show.

    SUPPORT and ADMIN both reach it. Support already decides registrations and bans, and a
    screen that lists nobody is not a smaller version of that permission, it is a broken page.
    """

    def __init__(self, user_repo: UserRepositoryPort):
        self._user_repo = user_repo

    async def execute(self, actor_role: Role, state: UserState | None = None) -> list[User]:
        if actor_role not in (Role.SUPPORT, Role.ADMIN):
            raise InvalidRoleTransitionError("Only SUPPORT or ADMIN can list the user directory.")
        return await self._user_repo.list_users(state)
