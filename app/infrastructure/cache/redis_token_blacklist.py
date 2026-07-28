import redis.asyncio as redis

from app.application.ports.auth_ports import TokenBlacklistPort
from app.config import settings

_BLACKLIST_KEY_PREFIX = "auth:revoked_jti:"


class RedisTokenBlacklist(TokenBlacklistPort):
    def __init__(self):
        self._client = redis.from_url(settings.redis_url, decode_responses=True)

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        await self._client.set(f"{_BLACKLIST_KEY_PREFIX}{jti}", "1", ex=ttl_seconds)

    async def is_revoked(self, jti: str) -> bool:
        return (await self._client.exists(f"{_BLACKLIST_KEY_PREFIX}{jti}")) == 1

    async def close(self) -> None:
        await self._client.aclose()
