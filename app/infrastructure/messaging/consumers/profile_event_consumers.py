import logging

from app.infrastructure.db.session import db_session_scope
from app.infrastructure.db.repositories.profile_repository import SqlAlchemyProfileRepository
from app.application.use_cases.profile.user_sync_projector import UserSyncProjector
from app.application.use_cases.profile.library_projector import LibraryProjector
from app.application.use_cases.profile.inventory_projector import InventoryProjector
from app.application.use_cases.profile.top_posts_projector import TopPostsProjector

logger = logging.getLogger(__name__)


async def handle_user_registered(event: dict) -> None:
    """Consumes UserRegistered (published by this same service's Auth part) to seed
    the Profile read-model row -> keeps Auth/Profile decoupled even though co-located."""
    if event.get("event_type") != "UserRegistered":
        return
    async with db_session_scope() as session:
        repo = SqlAlchemyProfileRepository(session)
        await UserSyncProjector(repo).handle(event)


async def handle_ownership_granted(event: dict) -> None:
    """Consumes OwnershipGranted from Store/Catalog -> updates owned-games library."""
    async with db_session_scope() as session:
        repo = SqlAlchemyProfileRepository(session)
        await LibraryProjector(repo).handle(event)


async def handle_item_or_trade_event(event: dict) -> None:
    """Consumes ItemGranted / TradeMatched from Marketplace -> updates item inventory."""
    async with db_session_scope() as session:
        repo = SqlAlchemyProfileRepository(session)
        await InventoryProjector(repo).handle(event)


async def handle_post_reacted(event: dict) -> None:
    """Consumes PostReacted-family events from Community/Forum -> updates top-5 posts."""
    async with db_session_scope() as session:
        repo = SqlAlchemyProfileRepository(session)
        await TopPostsProjector(repo).handle(event)
