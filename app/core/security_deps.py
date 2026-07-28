from dataclasses import dataclass
from typing import Iterable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.domain.auth.enums import Role
from app.domain.auth.exceptions import TokenError
from app.infrastructure.security.jwt_provider import JwtTokenProvider

_bearer_scheme = HTTPBearer(auto_error=True)
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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

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
