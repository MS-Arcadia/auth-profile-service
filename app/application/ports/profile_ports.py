from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.profile.profile import Profile
from app.domain.profile.value_objects import OwnedGame, OwnedItem, TopPost


class ProfileRepositoryPort(ABC):
    @abstractmethod
    async def get_by_user_id(self, user_id: str) -> Profile | None: ...

    @abstractmethod
    async def save(self, profile: Profile) -> None: ...

    @abstractmethod
    async def create_if_missing(self, user_id: str, display_name: str) -> Profile: ...

    @abstractmethod
    async def add_owned_game(self, owned_game: OwnedGame) -> None: ...

    @abstractmethod
    async def owns_game(self, user_id: str, game_id: str) -> bool:
        """Whether this library already lists the game.

        Exists because Kafka delivers at least once: without it a redelivered OwnershipGranted puts
        the same game in a library twice, and nothing on the row prevents that.
        """
        ...

    @abstractmethod
    async def remove_owned_game(self, user_id: str, game_id: str) -> None:
        """Take a game out of the library, for a refund or a defaulted instalment plan.

        A no-op when it is not there, which is what makes a redelivered revocation harmless.
        """
        ...

    @abstractmethod
    async def add_owned_item(self, owned_item: OwnedItem) -> None: ...

    @abstractmethod
    async def upsert_top_post(self, top_post: TopPost) -> None: ...

    @abstractmethod
    async def set_hidden(self, user_id: str, game_id: str, hidden: bool) -> None: ...


class PresenceStorePort(ABC):
    """Redis-backed real-time presence (SET EX / TTL heartbeat)."""

    @abstractmethod
    async def set_online(self, user_id: str, ttl_seconds: int) -> None: ...

    @abstractmethod
    async def is_online(self, user_id: str) -> bool: ...
