from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, List, Sequence

from app.domain.auth.user import User
from app.domain.auth.role_request import RoleRequest
from app.domain.auth.events import DomainEvent


class UserRepositoryPort(ABC):

    @abstractmethod
    async def get_by_id(self, user_id: str) -> Optional[User]: ...

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]: ...

    @abstractmethod
    async def save(self, user: User, outbox_events: Sequence[DomainEvent]) -> None:
        ...

    @abstractmethod
    async def record_login_audit(self, user_id: Optional[str], ip: str, success: bool) -> None: ...


class RoleRequestRepositoryPort(ABC):

    @abstractmethod
    async def get_role_request_by_id(self, request_id: str) -> Optional[RoleRequest]: ...

    @abstractmethod
    async def list_pending_role_requests(self) -> List[RoleRequest]: ...

    @abstractmethod
    async def save_role_request(self, role_request: RoleRequest, outbox_events: Sequence[DomainEvent]) -> None: ...


class JwtProviderPort(ABC):

    @abstractmethod
    def create_access_token(
        self, user_id: str, role: str, scopes: list[str] | None = None
    ) -> str:
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
