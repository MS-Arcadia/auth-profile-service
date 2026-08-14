from app.application.ports.auth_ports import UserRepositoryPort
from app.domain.auth.enums import UserState
from app.domain.auth.exceptions import RecipientNotFoundError, RecipientNotUniqueError
from app.domain.auth.user import User


class FindRecipientUseCase:
    """Resolve something a person can type into an account to send a gift to.

    A gift names somebody who is not the caller, and the only handle this platform has for
    that is an account id — a UUID. Asking a buyer to obtain their friend's UUID is not a
    feature, and the storefront's gift box did exactly that: it accepted whatever was typed
    and sent it as `recipient_id`, so a display name went through as an id, nothing checked
    it, and the game landed on an account that did not exist.

    Two ways in, in this order:

      - an **email**, which is unique and indexed. The one identifier that cannot be
        ambiguous, and the one people actually know about each other.
      - a **display name**, matched exactly and case-insensitively. Not unique, so two
        matches is reported as ambiguous rather than resolved to whichever came first —
        picking one is how a gift silently reaches a stranger with the same name.

    Deliberately not a search: exact matches only, no prefixes, no listing. It answers "is
    this specific person here" for somebody about to send them something, and refuses to be
    a way to enumerate the platform's users.

    Only ACTIVE accounts resolve. A gift to somebody pending approval or banned would be
    charged for and never usable.
    """

    def __init__(self, user_repo: UserRepositoryPort):
        self._user_repo = user_repo

    async def execute(self, query: str) -> User:
        candidate = query.strip()
        if not candidate:
            raise RecipientNotFoundError(query)

        if "@" in candidate:
            user = await self._user_repo.get_by_email(candidate.lower())
            if user is None or user.state is not UserState.ACTIVE:
                raise RecipientNotFoundError(candidate)
            return user

        matches = await self._user_repo.find_active_by_display_name(candidate)
        if not matches:
            raise RecipientNotFoundError(candidate)
        if len(matches) > 1:
            raise RecipientNotUniqueError(candidate, len(matches))
        return matches[0]
