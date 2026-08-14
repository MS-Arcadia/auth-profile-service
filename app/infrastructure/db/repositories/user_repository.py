import json
import uuid
from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.auth_ports import RoleRequestRepositoryPort, UserRepositoryPort
from app.domain.auth.enums import Role, RoleRequestStatus, UserState
from app.domain.auth.events import DomainEvent
from app.domain.auth.role_request import RoleRequest
from app.domain.auth.user import User
from app.infrastructure.db.models.login_audit_model import LoginAuditModel
from app.infrastructure.db.models.outbox_model import OutboxModel
from app.infrastructure.db.models.role_request_model import RoleRequestModel
from app.infrastructure.db.models.user_model import UserModel


def _to_domain_user(row: UserModel) -> User:
    return User(
        id=row.id,
        email=row.email,
        password_hash=row.password_hash,
        display_name=row.display_name,
        role=Role(row.role),
        state=UserState(row.state),
        created_at=row.created_at,
    )


def _to_domain_role_request(row: RoleRequestModel) -> RoleRequest:
    return RoleRequest(
        id=row.id,
        user_id=row.user_id,
        requested_role=Role(row.requested_role),
        status=RoleRequestStatus(row.status),
        decision_note=row.decision_note,
        decided_by=row.decided_by,
        created_at=row.created_at,
    )


def _like_fragment(query: str) -> str:
    """Escape LIKE metacharacters so a typed `%` or `_` is literal.

    `!` is the escape character (passed to SQLAlchemy as `escape='!'`). A
    backslash would fight PostgreSQL's own string escaping; bang does not.
    """
    return query.replace("!", "!!").replace("%", "!%").replace("_", "!_")


class SqlAlchemyUserRepository(UserRepositoryPort, RoleRequestRepositoryPort):
    def __init__(self, session: AsyncSession):
        self._session = session

    # ---- UserRepositoryPort ----
    async def get_by_id(self, user_id: str) -> User | None:
        row = await self._session.get(UserModel, user_id)
        return _to_domain_user(row) if row else None

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(UserModel).where(UserModel.email == email))
        row = result.scalar_one_or_none()
        return _to_domain_user(row) if row else None

    async def find_active_by_display_name(self, display_name: str) -> list[User]:
        """Active accounts whose display name matches exactly, case-insensitively.

        A list because `display_name` carries no unique constraint — two people may share
        one. The caller decides what to do about that rather than this silently picking the
        first, which is how a gift reaches the wrong person.
        """
        query = select(UserModel).where(
            func.lower(UserModel.display_name) == display_name.strip().lower(),
            UserModel.state == UserState.ACTIVE,
        )
        result = await self._session.execute(query)
        return [_to_domain_user(row) for row in result.scalars().all()]

    async def search_active(self, query: str, *, limit: int, exclude_user_id: str = "") -> list[User]:
        """Prefix search over ACTIVE accounts for the gift-box autocomplete.

        `!` is the LIKE escape so a typed `%` or `_` is a character, not a wildcard —
        otherwise `%%` would list everybody. Word-prefix (`% Farr%`) is how a last
        name finds `Nadia Farr` without turning this into a contains-search.
        """
        fragment = _like_fragment(query.strip())
        prefix = f"{fragment}%"
        word = f"% {fragment}%"
        conditions = [
            UserModel.state == UserState.ACTIVE,
            or_(
                UserModel.email.ilike(prefix, escape="!"),
                UserModel.display_name.ilike(prefix, escape="!"),
                UserModel.display_name.ilike(word, escape="!"),
            ),
        ]
        if exclude_user_id:
            conditions.append(UserModel.id != exclude_user_id)
        result = await self._session.execute(
            select(UserModel).where(*conditions).order_by(UserModel.display_name.asc()).limit(limit)
        )
        return [_to_domain_user(row) for row in result.scalars().all()]

    async def list_ids_by_state(self, state: UserState, role: Role | None = None) -> list[str]:
        query = select(UserModel.id).where(UserModel.state == state)
        if role is not None:
            query = query.where(UserModel.role == role)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def list_users(self, state: UserState | None = None) -> list[User]:
        """Every user, newest first, for the admin screen.

        Unpaginated on purpose for now: this is a platform with a few hundred accounts and one
        screen that shows them. Adding a page parameter that nothing passes would be machinery
        with no reader — the same mistake the outbox nobody subscribed to was.
        """
        query = select(UserModel).order_by(UserModel.created_at.desc())
        if state is not None:
            query = query.where(UserModel.state == state)
        result = await self._session.execute(query)
        return [_to_domain_user(row) for row in result.scalars().all()]

    async def save(self, user: User, outbox_events: Sequence[DomainEvent]) -> None:
        row = await self._session.get(UserModel, user.id)
        if row is None:
            row = UserModel(id=user.id)
            self._session.add(row)

        row.email = user.email
        row.password_hash = user.password_hash
        row.display_name = user.display_name
        row.role = user.role
        row.state = user.state
        row.created_at = user.created_at

        for event in outbox_events:
            self._session.add(
                OutboxModel(
                    id=str(uuid.uuid4()),
                    aggregate_type="User",
                    aggregate_id=user.id,
                    topic="user-events",
                    event_type=event.event_type,
                    payload=json.dumps(event.to_payload()),
                )
            )

        await self._session.commit()

    async def record_login_audit(self, user_id: str | None, ip: str, success: bool) -> None:
        self._session.add(LoginAuditModel(user_id=user_id, ip=ip, success=success))
        await self._session.commit()

    # ---- RoleRequestRepositoryPort ----
    async def get_role_request_by_id(self, request_id: str) -> RoleRequest | None:
        row = await self._session.get(RoleRequestModel, request_id)
        return _to_domain_role_request(row) if row else None

    async def list_pending_role_requests(self) -> list[RoleRequest]:
        result = await self._session.execute(
            select(RoleRequestModel).where(RoleRequestModel.status == RoleRequestStatus.PENDING)
        )
        return [_to_domain_role_request(r) for r in result.scalars().all()]

    async def save_role_request(self, role_request: RoleRequest, outbox_events: Sequence[DomainEvent]) -> None:
        row = await self._session.get(RoleRequestModel, role_request.id)
        if row is None:
            row = RoleRequestModel(id=role_request.id, user_id=role_request.user_id)
            self._session.add(row)

        row.requested_role = role_request.requested_role
        row.status = role_request.status
        row.decision_note = role_request.decision_note
        row.decided_by = role_request.decided_by
        row.created_at = role_request.created_at

        for event in outbox_events:
            self._session.add(
                OutboxModel(
                    id=str(uuid.uuid4()),
                    aggregate_type="RoleRequest",
                    aggregate_id=role_request.id,
                    topic="user-events",
                    event_type=event.event_type,
                    payload=json.dumps(event.to_payload()),
                )
            )

        await self._session.commit()
