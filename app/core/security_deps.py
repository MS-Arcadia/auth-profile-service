from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.domain.auth.enums import Role
from app.domain.auth.exceptions import TokenError
from app.infrastructure.security.jwt_provider import JwtTokenProvider

_bearer_scheme = HTTPBearer(auto_error=True)
_optional_bearer = HTTPBearer(auto_error=False)
_jwt_provider = JwtTokenProvider()


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    role: Role


def get_jwt_provider() -> JwtTokenProvider:
    return _jwt_provider


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> CurrentUser:
    try:
        claims = _jwt_provider.decode_access_token(credentials.credentials)
    except TokenError as exc:
        # `from exc` so the traceback shows which token check failed rather than presenting the
        # HTTPException as though it arose on its own inside the handler.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    return CurrentUser(user_id=claims["sub"], role=Role(claims["role"]))


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
) -> CurrentUser | None:
    """A signed-in caller if a token was sent, otherwise a visitor.

    Public profile pages are meant to be readable without an account. Requiring a
    bearer token made every unauthenticated GET 401, and the storefront rendered
    that as "Profile not found".
    """
    if credentials is None:
        return None
    try:
        claims = _jwt_provider.decode_access_token(credentials.credentials)
    except TokenError:
        return None
    return CurrentUser(user_id=claims["sub"], role=Role(claims["role"]))


def require_roles(*allowed_roles: Role):
    allowed: Iterable[Role] = allowed_roles

    async def _check(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role.value}' is not permitted to perform this action.",
            )
        return current_user

    return _check
