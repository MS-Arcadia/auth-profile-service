from app.application.ports.auth_ports import RoleRequestRepositoryPort
from app.domain.auth.enums import Role
from app.domain.auth.exceptions import InvalidRoleTransitionError


class ListPendingRoleRequestsUseCase:
    def __init__(self, role_request_repo: RoleRequestRepositoryPort):
        self._role_request_repo = role_request_repo

    async def execute(self, actor_role: Role):
        if actor_role not in (Role.SUPPORT, Role.ADMIN):
            raise InvalidRoleTransitionError(
                "Only SUPPORT or ADMIN can list pending role requests."
            )

        return await self._role_request_repo.list_pending_role_requests()