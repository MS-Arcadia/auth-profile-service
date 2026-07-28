from fastapi import APIRouter, Depends, status

from app.application.dto.auth_dto import (
    RequestRoleRequest, RoleRequestResponse, DecideRoleRequest,
    GrantRoleRequest, BanRequest,
)
from app.domain.auth.enums import Role
from app.application.use_cases.auth.request_role import RequestRoleUseCase
from app.application.use_cases.auth.decide_role_request import DecideRoleRequestUseCase
from app.application.use_cases.auth.approve_registration import ApproveRegistrationUseCase
from app.application.use_cases.auth.grant_role import GrantRoleUseCase
from app.application.use_cases.auth.ban_user import BanUserUseCase
from app.core.security_deps import get_current_user, require_roles, CurrentUser
from app.core.dependencies import (
    get_request_role_use_case, get_decide_role_request_use_case,
    get_approve_registration_use_case, get_grant_role_use_case, get_ban_user_use_case,
)

router = APIRouter(tags=["Roles & Admin"])


@router.post("/roles/request", response_model=RoleRequestResponse, status_code=status.HTTP_201_CREATED)
async def request_role(
    body: RequestRoleRequest,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: RequestRoleUseCase = Depends(get_request_role_use_case),
):
    """Any authenticated user requests to become DEVELOPER/SUPPORT, or requests a role change."""
    role_request = await use_case.execute(current_user.user_id, Role(body.requested_role))
    return RoleRequestResponse(request_id=role_request.id, status=role_request.status.value)


@router.post("/roles/{request_id}/decide", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(require_roles(Role.SUPPORT, Role.ADMIN))])
async def decide_role_request(
    request_id: str,
    body: DecideRoleRequest,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: DecideRoleRequestUseCase = Depends(get_decide_role_request_use_case),
):
    """SUPPORT/ADMIN approves or rejects a pending Developer/Support role request."""
    await use_case.execute(current_user.role, request_id, body.approve, current_user.user_id, body.note or "")


@router.post("/registrations/{user_id}/decide", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(require_roles(Role.SUPPORT, Role.ADMIN))])
async def decide_registration(
    user_id: str,
    body: DecideRoleRequest,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: ApproveRegistrationUseCase = Depends(get_approve_registration_use_case),
):
    await use_case.execute(
        current_user.role, user_id, body.approve, current_user.user_id, body.note or ""
    )


@router.post("/admin/users/{user_id}/grant-role", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(require_roles(Role.ADMIN))])
async def grant_role(
    user_id: str,
    body: GrantRoleRequest,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: GrantRoleUseCase = Depends(get_grant_role_use_case),
):
    await use_case.execute(current_user.role, user_id, Role(body.new_role), current_user.user_id)


@router.post("/admin/users/{user_id}/ban", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(require_roles(Role.SUPPORT, Role.ADMIN))])
async def ban_user(
    user_id: str,
    body: BanRequest,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: BanUserUseCase = Depends(get_ban_user_use_case),
):
    """SUPPORT/ADMIN bans a user (ACTIVE -> BANNED)."""
    await use_case.execute(current_user.role, user_id, True, current_user.user_id, body.reason or "")


@router.post("/admin/users/{user_id}/unban", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(require_roles(Role.SUPPORT, Role.ADMIN))])
async def unban_user(
    user_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: BanUserUseCase = Depends(get_ban_user_use_case),
):
    """SUPPORT/ADMIN unbans a user (BANNED -> ACTIVE)."""
    await use_case.execute(current_user.role, user_id, False, current_user.user_id)
