from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.application.use_cases.auth.login import LoginUseCase
from app.application.use_cases.auth.logout import LogoutUseCase
from app.application.use_cases.auth.refresh_token import RefreshTokenUseCase
from app.application.use_cases.auth.register_user import RegisterUserUseCase
from app.application.use_cases.auth.request_role import RequestRoleUseCase
from app.application.use_cases.profile.get_profile import GetProfileUseCase
from app.application.use_cases.profile.hide_game import HideGameUseCase
from app.application.use_cases.profile.set_avatar import SetAvatarUseCase
from app.application.use_cases.profile.update_presence import UpdatePresenceUseCase
from app.infrastructure.cache.redis_presence_store import RedisPresenceStore
from app.infrastructure.cache.redis_token_blacklist import RedisTokenBlacklist
from app.infrastructure.db.repositories.profile_repository import SqlAlchemyProfileRepository
from app.infrastructure.db.repositories.user_repository import SqlAlchemyUserRepository
from app.infrastructure.db.session import get_db_session
from app.infrastructure.messaging.kafka_producer import KafkaEventPublisher
from app.infrastructure.security.jwt_provider import JwtTokenProvider
from app.infrastructure.security.password_encoder import BcryptPasswordEncoder

_password_hasher = BcryptPasswordEncoder()
_jwt_provider = JwtTokenProvider()


# --- singleton adapters stored on app.state, exposed here for Depends() ---
def get_event_publisher(request: Request) -> KafkaEventPublisher:
    return request.app.state.event_publisher


def get_presence_store(request: Request) -> RedisPresenceStore:
    return request.app.state.presence_store


def get_token_blacklist(request: Request) -> RedisTokenBlacklist:
    return request.app.state.token_blacklist


# --- repositories (per-request, bound to the request's DB session) ---
def get_user_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemyUserRepository:
    return SqlAlchemyUserRepository(session)


def get_profile_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SqlAlchemyProfileRepository:
    return SqlAlchemyProfileRepository(session)


# --- Auth use cases ---
def get_register_user_use_case(
    user_repo: SqlAlchemyUserRepository = Depends(get_user_repository),
) -> RegisterUserUseCase:
    return RegisterUserUseCase(user_repo, _password_hasher)


def get_login_use_case(
    user_repo: SqlAlchemyUserRepository = Depends(get_user_repository),
) -> LoginUseCase:
    return LoginUseCase(user_repo, _password_hasher, _jwt_provider)


def get_refresh_token_use_case(
    user_repo: SqlAlchemyUserRepository = Depends(get_user_repository),
    token_blacklist: RedisTokenBlacklist = Depends(get_token_blacklist),
) -> RefreshTokenUseCase:
    return RefreshTokenUseCase(user_repo, _jwt_provider, token_blacklist)


def get_logout_use_case(
    token_blacklist: RedisTokenBlacklist = Depends(get_token_blacklist),
) -> LogoutUseCase:
    return LogoutUseCase(_jwt_provider, token_blacklist)


def get_approve_registration_use_case(
    user_repo: SqlAlchemyUserRepository = Depends(get_user_repository),
) -> ApproveRegistrationUseCase:
    return ApproveRegistrationUseCase(user_repo)


def get_grant_role_use_case(
    user_repo: SqlAlchemyUserRepository = Depends(get_user_repository),
) -> GrantRoleUseCase:
    return GrantRoleUseCase(user_repo)


def get_request_role_use_case(
    user_repo: SqlAlchemyUserRepository = Depends(get_user_repository),
) -> RequestRoleUseCase:
    return RequestRoleUseCase(user_repo, user_repo)


def get_decide_role_request_use_case(
    user_repo: SqlAlchemyUserRepository = Depends(get_user_repository),
) -> DecideRoleRequestUseCase:
    return DecideRoleRequestUseCase(user_repo, user_repo)


def get_ban_user_use_case(
    user_repo: SqlAlchemyUserRepository = Depends(get_user_repository),
) -> BanUserUseCase:
    return BanUserUseCase(user_repo)


def get_list_users_use_case(
    user_repo: SqlAlchemyUserRepository = Depends(get_user_repository),
) -> ListUsersUseCase:
    return ListUsersUseCase(user_repo)


def get_find_recipient_use_case(
    user_repo: SqlAlchemyUserRepository = Depends(get_user_repository),
) -> FindRecipientUseCase:
    return FindRecipientUseCase(user_repo)


def get_list_active_user_ids_use_case(
    user_repo: SqlAlchemyUserRepository = Depends(get_user_repository),
) -> ListActiveUserIdsUseCase:
    return ListActiveUserIdsUseCase(user_repo)


# --- Profile use cases ---
def get_profile_use_case(
    profile_repo: SqlAlchemyProfileRepository = Depends(get_profile_repository),
    presence_store: RedisPresenceStore = Depends(get_presence_store),
) -> GetProfileUseCase:
    return GetProfileUseCase(profile_repo, presence_store)


def get_update_presence_use_case(
    presence_store: RedisPresenceStore = Depends(get_presence_store),
    event_publisher: KafkaEventPublisher = Depends(get_event_publisher),
) -> UpdatePresenceUseCase:
    return UpdatePresenceUseCase(presence_store, event_publisher)


def get_hide_game_use_case(
    profile_repo: SqlAlchemyProfileRepository = Depends(get_profile_repository),
) -> HideGameUseCase:
    return HideGameUseCase(profile_repo)


def get_set_avatar_use_case(
    profile_repo: SqlAlchemyProfileRepository = Depends(get_profile_repository),
) -> SetAvatarUseCase:
    return SetAvatarUseCase(profile_repo)


def get_list_pending_role_requests_use_case(
    user_repo: SqlAlchemyUserRepository = Depends(get_user_repository),
) -> ListPendingRoleRequestsUseCase:
    return ListPendingRoleRequestsUseCase(user_repo)
