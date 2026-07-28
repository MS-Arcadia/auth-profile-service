from app.domain.auth.exceptions import TokenError, UserNotFoundError
from app.application.ports.auth_ports import UserRepositoryPort, JwtProviderPort, TokenBlacklistPort


class RefreshTokenUseCase:

    def __init__(
        self,
        user_repo: UserRepositoryPort,
        jwt_provider: JwtProviderPort,
        token_blacklist: TokenBlacklistPort,
    ):
        self._user_repo = user_repo
        self._jwt = jwt_provider
        self._blacklist = token_blacklist

    async def execute(self, refresh_token: str) -> str:
        try:
            claims = self._jwt.decode_refresh_token(refresh_token)
        except Exception as exc:
            raise TokenError("Invalid refresh token.") from exc

        jti = claims.get("jti")
        if jti and await self._blacklist.is_revoked(jti):
            raise TokenError("Refresh token has been revoked.")

        user_id = claims["sub"]
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        if not user.can_login():
            raise TokenError("Account is not active.")

        return self._jwt.create_access_token(user.id, user.role.value)
