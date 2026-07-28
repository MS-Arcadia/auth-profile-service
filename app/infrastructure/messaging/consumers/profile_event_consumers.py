"""Consumers that build the Profile read-model from other services' events.

Each handler takes a whole platform message, routes on `event_type`, and reads the domain fields
out of `payload`. Both of those were wrong before: the handlers read the top level of the message,
and one compared `event_type` against a bare class name.

The topics are shared. `game-events` carries every catalog change, not only ownership — so routing
is what stops the library projector acting on a game being withdrawn.
"""

import logging

from app.application.use_cases.profile.inventory_projector import InventoryProjector
from app.application.use_cases.profile.library_projector import LibraryProjector
from app.application.use_cases.profile.top_posts_projector import TopPostsProjector
from app.application.use_cases.profile.user_sync_projector import UserSyncProjector
from app.infrastructure.db.repositories.profile_repository import SqlAlchemyProfileRepository
from app.infrastructure.db.session import db_session_scope
from app.infrastructure.messaging.envelope import route

logger = logging.getLogger(__name__)

# The names other services actually publish. Fully qualified, because that is what is on the wire —
# a bare "UserRegistered" matches nothing.
AUTH_USER_REGISTERED = "arcadia.auth.v1.UserRegistered"
CATALOG_OWNERSHIP_GRANTED = "arcadia.catalog.v1.OwnershipGranted"
CATALOG_OWNERSHIP_REVOKED = "arcadia.catalog.v1.OwnershipRevoked"
# Marketplace and Community do not exist yet. These are the names their events will carry, so this
# service starts consuming them the day they ship rather than needing a change here.
MARKETPLACE_ITEM_GRANTED = "arcadia.marketplace.v1.ItemGranted"
MARKETPLACE_TRADE_MATCHED = "arcadia.marketplace.v1.TradeMatched"
COMMUNITY_POST_REACTED = "arcadia.community.v1.PostReacted"


async def _dispatch(message: dict, handlers: dict) -> None:
    routed = route(message, handlers)
    if routed is None:
        return
    envelope, handler = routed
    await handler(envelope.payload)


async def handle_user_events(message: dict) -> None:
    """Seeds the Profile row from this service's own Auth half.

    Auth and Profile share a deployment and still talk only through events, which is what keeps
    them separable later. It also means the Profile row appears a moment after registration rather
    than in the same transaction — acceptable, because the only person who reads a profile that
    new is its owner, who has just registered.
    """
    await _dispatch(message, {AUTH_USER_REGISTERED: _project_user})


async def handle_game_events(message: dict) -> None:
    """Keeps the owned-games library in step with the catalog."""
    await _dispatch(
        message,
        {
            CATALOG_OWNERSHIP_GRANTED: _project_ownership_granted,
            CATALOG_OWNERSHIP_REVOKED: _project_ownership_revoked,
        },
    )


async def handle_marketplace_events(message: dict) -> None:
    await _dispatch(
        message,
        {
            MARKETPLACE_ITEM_GRANTED: _project_inventory,
            MARKETPLACE_TRADE_MATCHED: _project_inventory,
        },
    )


async def handle_community_events(message: dict) -> None:
    await _dispatch(message, {COMMUNITY_POST_REACTED: _project_top_posts})


# --- the projections themselves -----------------------------------------


async def _project_user(payload: dict) -> None:
    async with db_session_scope() as session:
        await UserSyncProjector(SqlAlchemyProfileRepository(session)).handle(payload)


async def _project_ownership_granted(payload: dict) -> None:
    async with db_session_scope() as session:
        await LibraryProjector(SqlAlchemyProfileRepository(session)).handle(payload)


async def _project_ownership_revoked(payload: dict) -> None:
    """A refund, or an instalment plan that defaulted, takes the game back.

    Without this the library keeps a game its owner no longer has. The catalog is the authority on
    ownership, so a read-model that disagrees with it is the read-model being wrong.
    """
    async with db_session_scope() as session:
        await LibraryProjector(SqlAlchemyProfileRepository(session)).revoke(payload)


async def _project_inventory(payload: dict) -> None:
    async with db_session_scope() as session:
        await InventoryProjector(SqlAlchemyProfileRepository(session)).handle(payload)


async def _project_top_posts(payload: dict) -> None:
    async with db_session_scope() as session:
        await TopPostsProjector(SqlAlchemyProfileRepository(session)).handle(payload)
