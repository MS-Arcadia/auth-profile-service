from app.application.ports.auth_ports import RoleRequestRepositoryPort, UserRepositoryPort
from app.domain.auth.enums import Role
from app.domain.auth.events import RoleRequested
from app.domain.auth.exceptions import InvalidRoleTransitionError, UserNotFoundError
from app.domain.auth.role_policy import RolePolicy
from app.domain.auth.role_request import RoleRequest


class RequestRoleUseCase:
    def __init__(self, user_repo: UserRepositoryPort, role_request_repo: RoleRequestRepositoryPort):
        self._user_repo = user_repo
        self._role_request_repo = role_request_repo

    async def execute(self, user_id: str, requested_role: Role) -> RoleRequest:
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)

        if not RolePolicy.can_request(user.role, requested_role):
            raise InvalidRoleTransitionError(
                f"User with role '{user.role.value}' cannot request role '{requested_role.value}'."
            )

        role_request = RoleRequest.create(user_id=user_id, requested_role=requested_role)
        event = RoleRequested(request_id=role_request.id, user_id=user_id, requested_role=requested_role.value)

        await self._role_request_repo.save_role_request(role_request, [event])
        return role_request
