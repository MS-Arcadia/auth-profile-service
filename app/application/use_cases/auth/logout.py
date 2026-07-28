from app.application.ports.auth_ports import JwtProviderPort, TokenBlacklistPort


class LogoutUseCase:

    def __init__(self, jwt_provider: JwtProviderPort, token_blacklist: TokenBlacklistPort):
        self._jwt = jwt_provider
        self._blacklist = token_blacklist

    async def execute(self, refresh_token: str) -> None:
        claims = self._jwt.decode_refresh_token(refresh_token)
        jti = claims.get("jti")
        exp = claims.get("exp")
        if not jti or not exp:
            return
        import time
        ttl = max(int(exp - time.time()), 1)
        await self._blacklist.revoke(jti, ttl)
