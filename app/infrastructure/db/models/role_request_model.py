import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.auth.enums import Role, RoleRequestStatus
from app.infrastructure.db.base import Base


class RoleRequestModel(Base):
    __tablename__ = "role_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    requested_role: Mapped[Role] = mapped_column(
        SAEnum(Role, name="requested_role_enum"), nullable=False
    )
    status: Mapped[RoleRequestStatus] = mapped_column(
        SAEnum(RoleRequestStatus, name="role_request_status_enum"),
        nullable=False,
        default=RoleRequestStatus.PENDING,
    )
    decision_note: Mapped[str | None] = mapped_column(String(512), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
