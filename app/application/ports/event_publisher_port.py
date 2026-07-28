from abc import ABC, abstractmethod


class EventPublisherPort(ABC):
    @abstractmethod
    async def publish(self, topic: str, key: str, payload: dict) -> None: ...
