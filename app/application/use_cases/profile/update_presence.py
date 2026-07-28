from app.application.ports.event_publisher_port import EventPublisherPort
from app.application.ports.profile_ports import PresenceStorePort
from app.domain.profile.events import PresenceChanged

PRESENCE_TTL_SECONDS = 30


class UpdatePresenceUseCase:
    def __init__(self, presence_store: PresenceStorePort, event_publisher: EventPublisherPort):
        self._presence_store = presence_store
        self._event_publisher = event_publisher

    async def execute(self, user_id: str) -> None:
        was_online = await self._presence_store.is_online(user_id)
        await self._presence_store.set_online(user_id, ttl_seconds=PRESENCE_TTL_SECONDS)

        if not was_online:
            event = PresenceChanged(user_id=user_id, online=True)
            await self._event_publisher.publish(
                topic="presence-events",
                key=user_id,
                payload={"event_type": event.event_type, **event.__dict__},
            )
