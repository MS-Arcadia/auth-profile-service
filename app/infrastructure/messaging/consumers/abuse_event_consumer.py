import logging

from sqlalchemy import select

from app.infrastructure.db.session import db_session_scope
from app.infrastructure.db.models.user_model import UserModel

logger = logging.getLogger(__name__)


class AbuseEventConsumer:

    async def handle(self, event: dict) -> None:
        user_id = event.get("user_id")
        if not user_id:
            logger.warning("GiftCardAbuseDetected event missing user_id: %s", event)
            return

        async with db_session_scope() as session:
            row = await session.execute(select(UserModel).where(UserModel.id == user_id))
            user = row.scalar_one_or_none()
            if user is None:
                logger.warning("GiftCardAbuseDetected for unknown user_id=%s", user_id)
                return

            logger.warning(
                "FLAGGED FOR SUPPORT REVIEW: user_id=%s email=%s reason=%s (no auto-ban applied)",
                user.id, user.email, event.get("reason", "gift-card abuse pattern"),
            )
