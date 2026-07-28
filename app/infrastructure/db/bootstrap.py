import logging

from app.config import settings
from app.infrastructure.db.repositories.user_repository import SqlAlchemyUserRepository
from app.infrastructure.db.session import db_session_scope
from app.infrastructure.security.password_encoder import BcryptPasswordEncoder

logger = logging.getLogger(__name__)


async def seed_super_admin() -> None:
    hasher = BcryptPasswordEncoder()

    async with db_session_scope() as session:
        repo = SqlAlchemyUserRepository(session)
        existing = await repo.get_by_email(settings.super_admin_email)
        if existing is not None:
            logger.info(
                "Super-Admin already exists (email=%s) - skipping seed", settings.super_admin_email
            )
            return

        from app.domain.auth.user import User

        admin = User.register_super_admin(
            email=settings.super_admin_email,
            password_hash=hasher.hash(settings.super_admin_password),
            display_name=settings.super_admin_display_name,
        )
        events = admin.pull_events()
        await repo.save(admin, events)
        logger.warning(
            "Seeded Super-Admin account email=%s - CHANGE THE DEFAULT PASSWORD IMMEDIATELY",
            settings.super_admin_email,
        )
