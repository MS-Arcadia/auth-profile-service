from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.domain.auth.enums import Role, UserState
from app.domain.auth.events import DomainEvent
from app.domain.auth.role_request import RoleRequest
from app.domain.auth.user import User


class UserRepositoryPort(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: str) -> User | None: ...

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def list_users(self, state: UserState | None = None) -> list[User]:
        """Every user, for the admin screen that grants roles and bans accounts."""
        ...

    @abstractmethod
    async def find_active_by_display_name(self, display_name: str) -> list[User]:
        """Active accounts with exactly this display name. A list, because it is not unique."""
        ...

    @abstractmethod
    async def search_active(self, query: str, *, limit: int, exclude_user_id: str = "") -> list[User]:
        """ACTIVE accounts whose email or display name starts with `query`.

        Also matches a later word of the display name (`Farr` → `Nadia Farr`), so a
        last name is enough to type. Prefix, not contains — `dia` must not list Nadia.
        `exclude_user_id` drops the caller so they are not suggested themselves.
        """
        ...

    @abstractmethod
    async def list_ids_by_state(self, state: UserState, role: Role | None = None) -> list[str]:
        """Return the ids of every user in the given state.

        Exists for platform-wide broadcasts (e.g. a festival going live, which is meant to
        notify every active user): the caller needs the full audience, not a page of it, so
        this returns ids only rather than a paginated list of full `User` records.
        """
        ...

    @abstractmethod
    async def save(self, user: User, outbox_events: Sequence[DomainEvent]) -> None: ...

    @abstractmethod
    async def record_login_audit(self, user_id: str | None, ip: str, success: bool) -> None: ...


class RoleRequestRepositoryPort(ABC):
    @abstractmethod
    async def get_role_request_by_id(self, request_id: str) -> RoleRequest | None: ...

    @abstractmethod
    async def list_pending_role_requests(self) -> list[RoleRequest]: ...

    @abstractmethod
    async def save_role_request(self, role_request: RoleRequest, outbox_events: Sequence[DomainEvent]) -> None: ...


class JwtProviderPort(ABC):
    @abstractmethod
    def create_access_token(self, user_id: str, role: str, scopes: list[str] | None = None) -> str:
        """Mint an access token in the platform's claim shape.

        `scopes` is optional and empty for a human login. It exists because the media service
        already reads `media:read` off a token to let one service read another's private objects,
        and a port that could not express that would force the caller around it.
        """
        ...

    @abstractmethod
    def create_refresh_token(self, user_id: str) -> str: ...

    @abstractmethod
    def decode_access_token(self, token: str) -> dict: ...

    @abstractmethod
    def decode_refresh_token(self, token: str) -> dict: ...


class PasswordHasherPort(ABC):
    @abstractmethod
    def hash(self, plain_password: str) -> str: ...

    @abstractmethod
    def verify(self, plain_password: str, password_hash: str) -> bool: ...


class TokenBlacklistPort(ABC):
    @abstractmethod
    async def revoke(self, jti: str, ttl_seconds: int) -> None: ...

    @abstractmethod
    async def is_revoked(self, jti: str) -> bool: ...
