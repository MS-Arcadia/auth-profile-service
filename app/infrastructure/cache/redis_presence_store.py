import redis.asyncio as redis

from app.application.ports.profile_ports import PresenceStorePort
from app.config import settings

_PRESENCE_KEY_PREFIX = "presence:online:"


class RedisPresenceStore(PresenceStorePort):
    """Real-time online/offline presence via Redis TTL keys (SET EX).
    A user is 'online' as long as their key hasn't expired between heartbeats."""

    def __init__(self):
        self._client = redis.from_url(settings.redis_url, decode_responses=True)

    async def set_online(self, user_id: str, ttl_seconds: int) -> None:
        await self._client.set(f"{_PRESENCE_KEY_PREFIX}{user_id}", "1", ex=ttl_seconds)

    async def is_online(self, user_id: str) -> bool:
        return (await self._client.exists(f"{_PRESENCE_KEY_PREFIX}{user_id}")) == 1

    async def ping(self) -> None:
        """Raise if Redis is unreachable. Read by the readiness probe, which reports this as
        degraded rather than down — presence going stale is not worth refusing logins over."""
        await self._client.ping()

    async def close(self) -> None:
        await self._client.aclose()
