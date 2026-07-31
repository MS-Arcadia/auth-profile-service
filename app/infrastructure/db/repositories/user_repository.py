import json
import uuid
from collections.abc import Sequence

from sqlalchemy import select
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

    async def list_ids_by_state(self, state: UserState) -> list[str]:
        result = await self._session.execute(select(UserModel.id).where(UserModel.state == state))
        return list(result.scalars().all())

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
