"""Projects the catalog's ownership events into the profile's game library.

Three things here were wrong or missing, and each only shows up against a real platform.

**The field name.** The catalog publishes `owner_id`, not `user_id` — for a gift the buyer and the
owner are different people, and the library belongs to the owner. This read `event["user_id"]` and
raised `KeyError` on every real event.

**Idempotency.** Kafka delivers at least once and the consumer retries three times, so a projector
that inserts unconditionally puts the same game in a library twice. Nothing on the row prevents it,
so the check is explicit.

**Revocation.** A refund and a defaulted instalment plan both revoke ownership, and this only ever
added. A library that keeps a game its owner no longer has is a read-model contradicting the
service that owns the fact.
"""

import uuid

from app.application.ports.profile_ports import ProfileRepositoryPort
from app.domain.profile.value_objects import OwnedGame


class LibraryProjector:
    def __init__(self, profile_repo: ProfileRepositoryPort):
        self._profile_repo = profile_repo

    async def handle(self, payload: dict) -> None:
        """`arcadia.catalog.v1.OwnershipGranted` — the recipient now owns the game."""
        user_id = _owner_of(payload)
        game_id = str(payload.get("game_id") or "")
        if not user_id or not game_id:
            # Refused rather than half-projected. A row with an empty user or game is invisible to
            # every query and impossible to explain later.
            raise ValueError(f"OwnershipGranted needs an owner and a game, got {payload!r}")

        # The profile row may not exist yet: a purchase can complete before this service has
        # processed its own UserRegistered, because the two arrive on different topics.
        await self._profile_repo.create_if_missing(user_id, display_name="")

        if await self._profile_repo.owns_game(user_id, game_id):
            return

        await self._profile_repo.add_owned_game(OwnedGame(id=str(uuid.uuid4()), user_id=user_id, game_id=game_id))

    async def revoke(self, payload: dict) -> None:
        """`arcadia.catalog.v1.OwnershipRevoked` — a refund, or an instalment plan that defaulted.

        Idempotent by nature: removing something already gone is a no-op, which is what makes a
        redelivered revocation harmless.
        """
        user_id = _owner_of(payload)
        game_id = str(payload.get("game_id") or "")
        if not user_id or not game_id:
            raise ValueError(f"OwnershipRevoked needs an owner and a game, got {payload!r}")
        await self._profile_repo.remove_owned_game(user_id, game_id)


def _owner_of(payload: dict) -> str:
    """The catalog's field is `owner_id`.

    `user_id` is accepted as a fallback so a producer that spells it the other way still projects
    rather than silently doing nothing — but `owner_id` is the contract, and the distinction
    matters: for a gift the buyer and the owner are different people.
    """
    return str(payload.get("owner_id") or payload.get("user_id") or "")
