from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional

from app.domain.profile.profile import Profile
from app.domain.profile.value_objects import OwnedGame, OwnedItem, TopPost


class ProfileRepositoryPort(ABC):

    @abstractmethod
    async def get_by_user_id(self, user_id: str) -> Optional[Profile]: ...

    @abstractmethod
    async def save(self, profile: Profile) -> None: ...

    @abstractmethod
    async def create_if_missing(self, user_id: str, display_name: str) -> Profile: ...

    @abstractmethod
    async def add_owned_game(self, owned_game: OwnedGame) -> None: ...

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
