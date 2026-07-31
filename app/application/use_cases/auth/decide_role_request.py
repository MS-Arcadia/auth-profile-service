from app.application.ports.auth_ports import RoleRequestRepositoryPort, UserRepositoryPort
from app.domain.auth.enums import Role
from app.domain.auth.exceptions import RoleRequestNotFoundError
from app.domain.auth.role_policy import RolePolicy


class DecideRoleRequestUseCase:
    def __init__(self, user_repo: UserRepositoryPort, role_request_repo: RoleRequestRepositoryPort):
        self._user_repo = user_repo
        self._role_request_repo = role_request_repo

    async def execute(self, actor_role: Role, request_id: str, approve: bool, decided_by: str, note: str = "") -> None:
        RolePolicy.assert_can_decide_role_request(actor_role)

        role_request = await self._role_request_repo.get_role_request_by_id(request_id)
        if role_request is None:
            raise RoleRequestNotFoundError(request_id)

        events = []
        if approve:
            role_request.approve(decided_by, note)
            user = await self._user_repo.get_by_id(role_request.user_id)
            # `change_role` records the previous role on the RoleGranted event it raises, so
            # capturing it here was dead — and a reader would reasonably assume it was needed.
            user.change_role(role_request.requested_role, granted_by=decided_by)
            user_events = user.pull_events()
            await self._user_repo.save(user, user_events)
        else:
            role_request.reject(decided_by, note)

        await self._role_request_repo.save_role_request(role_request, events)
