import logging

from sqlalchemy import select

from app.infrastructure.db.session import db_session_scope
from app.infrastructure.db.models.user_model import UserModel
from app.infrastructure.messaging.envelope import route

logger = logging.getLogger(__name__)


# The wallet's event, fully qualified. `wallet-events` carries every balance movement on the
# platform, so without this filter every debit and credit would be treated as an abuse report.
GIFT_CARD_ABUSE_DETECTED = "arcadia.wallet.v1.GiftCardAbuseDetected"


class AbuseEventConsumer:
    """Flags a user for Support after repeated bad gift-card codes (requirement 1.5).

    Only flags. The wallet publishes the detection and deliberately bans nobody; the requirement
    says a ban is at Support's discretion, so an automatic one here would be the platform deciding
    something a human was asked to decide.
    """

    async def handle(self, message: dict) -> None:
        routed = route(message, {GIFT_CARD_ABUSE_DETECTED: self._flag})
        if routed is None:
            return
        envelope, handler = routed
        await handler(envelope.payload)

    async def _flag(self, payload: dict) -> None:
        # From the payload, not the top level. This read `event.get("user_id")` against a platform
        # envelope, where that is always None — so every message it ever saw was logged as
        # "missing user_id" and nobody was ever flagged.
        user_id = payload.get("user_id")
        if not user_id:
            logger.warning("GiftCardAbuseDetected carried no user_id: %s", payload)
            return

        async with db_session_scope() as session:
            row = await session.execute(select(UserModel).where(UserModel.id == user_id))
            user = row.scalar_one_or_none()
            if user is None:
                logger.warning("GiftCardAbuseDetected for unknown user_id=%s", user_id)
                return

            logger.warning(
                "FLAGGED FOR SUPPORT REVIEW: user_id=%s email=%s reason=%s (no auto-ban applied)",
                user.id, user.email, payload.get("reason", "gift-card abuse pattern"),
            )
