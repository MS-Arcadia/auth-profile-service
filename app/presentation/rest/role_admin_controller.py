from fastapi import APIRouter, Depends, Query, status

from app.application.dto.auth_dto import (
    AdminUserResponse,
    BanRequest,
    DecideRoleRequest,
    GrantRoleRequest,
    PendingRoleRequestResponse,
    RecipientResponse,
    RequestRoleRequest,
    RoleRequestResponse,
)
from app.application.use_cases.auth.approve_registration import ApproveRegistrationUseCase
from app.application.use_cases.auth.ban_user import BanUserUseCase
from app.application.use_cases.auth.decide_role_request import DecideRoleRequestUseCase
from app.application.use_cases.auth.find_recipient import FindRecipientUseCase
from app.application.use_cases.auth.grant_role import GrantRoleUseCase
from app.application.use_cases.auth.list_active_user_ids import ListActiveUserIdsUseCase
from app.application.use_cases.auth.list_pending_role_requests import (
    ListPendingRoleRequestsUseCase,
)
from app.application.use_cases.auth.list_users import ListUsersUseCase
from app.application.use_cases.auth.request_role import RequestRoleUseCase
from app.core.dependencies import (
    get_approve_registration_use_case,
    get_ban_user_use_case,
    get_decide_role_request_use_case,
    get_find_recipient_use_case,
    get_grant_role_use_case,
    get_list_active_user_ids_use_case,
    get_list_pending_role_requests_use_case,
    get_list_users_use_case,
    get_request_role_use_case,
)
from app.core.security_deps import CurrentUser, get_current_user, require_roles
from app.domain.auth.enums import Role, UserState

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


@router.post(
    "/roles/{request_id}/decide",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(Role.SUPPORT, Role.ADMIN))],
)
async def decide_role_request(
    request_id: str,
    body: DecideRoleRequest,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: DecideRoleRequestUseCase = Depends(get_decide_role_request_use_case),
):
    """SUPPORT/ADMIN approves or rejects a pending Developer/Support role request."""
    await use_case.execute(current_user.role, request_id, body.approve, current_user.user_id, body.note or "")


@router.post(
    "/registrations/{user_id}/decide",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(Role.SUPPORT, Role.ADMIN))],
)
async def decide_registration(
    user_id: str,
    body: DecideRoleRequest,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: ApproveRegistrationUseCase = Depends(get_approve_registration_use_case),
):
    await use_case.execute(current_user.role, user_id, body.approve, current_user.user_id, body.note or "")


@router.post(
    "/admin/users/{user_id}/grant-role",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(Role.ADMIN))],
)
async def grant_role(
    user_id: str,
    body: GrantRoleRequest,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: GrantRoleUseCase = Depends(get_grant_role_use_case),
):
    await use_case.execute(current_user.role, user_id, Role(body.new_role), current_user.user_id)


@router.post(
    "/admin/users/{user_id}/ban",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(Role.SUPPORT, Role.ADMIN))],
)
async def ban_user(
    user_id: str,
    body: BanRequest,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: BanUserUseCase = Depends(get_ban_user_use_case),
):
    """SUPPORT/ADMIN bans a user (ACTIVE -> BANNED)."""
    await use_case.execute(current_user.role, user_id, True, current_user.user_id, body.reason or "")


@router.get("/users/lookup", response_model=RecipientResponse)
async def lookup_recipient(
    q: str = Query(min_length=1, max_length=255, description="An email address, or an exact display name"),
    _current_user: CurrentUser = Depends(get_current_user),
    use_case: FindRecipientUseCase = Depends(get_find_recipient_use_case),
):
    """Find the person a gift is for.

    A gift is addressed by account id — a UUID — and nobody knows their friend's UUID. The
    storefront's gift box asked for one anyway and sent whatever was typed, so a display
    name went through as an id, nothing checked it, and the game landed on an account that
    did not exist while the buyer was charged in full.

    Any signed-in account may ask, because anyone may send a gift. It is deliberately not a
    search: exact email or exact display name, one result or none. That answers "is this
    specific person here" for somebody about to send them something without becoming a way
    to enumerate the platform.
    """
    user = await use_case.execute(q)
    return RecipientResponse(user_id=user.id, display_name=user.display_name)


@router.get(
    "/admin/users",
    response_model=list[AdminUserResponse],
    dependencies=[Depends(require_roles(Role.SUPPORT, Role.ADMIN))],
)
async def list_users(
    user_state: UserState | None = Query(None, alias="status"),
    current_user: CurrentUser = Depends(get_current_user),
    use_case: ListUsersUseCase = Depends(get_list_users_use_case),
):
    """The admin screen's directory: every account, with enough of each to act on it.

    `/admin/users/ids` answers a different question — "who is everybody", for a platform-wide
    broadcast — and returns bare ids. A person deciding whether to grant a role or ban somebody
    needs the name, the email, the role and the state, which an id list cannot show. The
    storefront was calling a `/admin/users` that did not exist, so the screen listed nobody
    while its ban and grant-role buttons worked perfectly on people it could not display.
    """
    users = await use_case.execute(current_user.role, user_state)
    return [
        AdminUserResponse(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role.value,
            state=user.state.value,
            created_at=user.created_at,
        )
        for user in users
    ]


@router.get(
    "/admin/users/ids",
    response_model=list[str],
    dependencies=[Depends(require_roles(Role.SUPPORT, Role.ADMIN))],
)
async def list_user_ids(
    user_state: UserState = Query(UserState.ACTIVE, alias="status"),
    role: Role | None = Query(None),
    current_user: CurrentUser = Depends(get_current_user),
    use_case: ListActiveUserIdsUseCase = Depends(get_list_active_user_ids_use_case),
):
    """Internal directory lookup: every user id in the given state (default ACTIVE).

    Meant for service-to-service calls that need "everyone" — e.g. festival-service
    populating a platform-wide `FestivalStarted` notification audience — not for browser
    clients, hence living under `/admin` next to the other SUPPORT/ADMIN-only routes.

    `role` narrows it to one role. notification-service uses that to address the people
    who can act on something — a game waiting for review goes to SUPPORT, not to everyone.
    """
    return await use_case.execute(current_user.role, user_state, role)


@router.post(
    "/admin/users/{user_id}/unban",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(Role.SUPPORT, Role.ADMIN))],
)
async def unban_user(
    user_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: BanUserUseCase = Depends(get_ban_user_use_case),
):
    """SUPPORT/ADMIN unbans a user (BANNED -> ACTIVE)."""
    await use_case.execute(current_user.role, user_id, False, current_user.user_id)


@router.get(
    "/admin/role-requests/pending",
    response_model=list[PendingRoleRequestResponse],
    dependencies=[Depends(require_roles(Role.SUPPORT, Role.ADMIN))],
)
async def list_pending_role_requests(
    current_user: CurrentUser = Depends(get_current_user),
    use_case: ListPendingRoleRequestsUseCase = Depends(get_list_pending_role_requests_use_case),
):
    """Return all pending role requests for SUPPORT/ADMIN."""
    role_requests = await use_case.execute(current_user.role)

    return [
        PendingRoleRequestResponse(
            request_id=request.id,
            user_id=request.user_id,
            requested_role=request.requested_role.value,
            status=request.status.value,
            decision_note=request.decision_note,
            decided_by=request.decided_by,
            created_at=request.created_at,
        )
        for request in role_requests
    ]
