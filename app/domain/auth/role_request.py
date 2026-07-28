from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid

from app.domain.auth.enums import Role, RoleRequestStatus
from app.domain.auth.exceptions import RoleRequestAlreadyDecidedError


@dataclass
class RoleRequest:
    id: str
    user_id: str
    requested_role: Role
    status: RoleRequestStatus
    decision_note: Optional[str] = None
    decided_by: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @staticmethod
    def create(user_id: str, requested_role: Role) -> "RoleRequest":
        return RoleRequest(
            id=str(uuid.uuid4()),
            user_id=user_id,
            requested_role=requested_role,
            status=RoleRequestStatus.PENDING,
        )

    def approve(self, decided_by: str, note: Optional[str] = None) -> None:
        if self.status != RoleRequestStatus.PENDING:
            raise RoleRequestAlreadyDecidedError(self.id)
        self.status = RoleRequestStatus.APPROVED
        self.decided_by = decided_by
        self.decision_note = note

    def reject(self, decided_by: str, note: Optional[str] = None) -> None:
        if self.status != RoleRequestStatus.PENDING:
            raise RoleRequestAlreadyDecidedError(self.id)
        self.status = RoleRequestStatus.REJECTED
        self.decided_by = decided_by
        self.decision_note = note
