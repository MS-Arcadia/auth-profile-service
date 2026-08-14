from app.application.ports.auth_ports import UserRepositoryPort
from app.domain.auth.user import User

MIN_QUERY_LENGTH = 2
MAX_RESULTS = 8


class SuggestRecipientsUseCase:
    """Prefix suggestions for the gift box, as the sender types.

    Lookup stays exact — it answers "is this specific person here". This is the
    autocomplete that lookup refused to become: a short, authenticated list of
    ACTIVE accounts whose email or display name starts with what was typed (or
    whose name has a word that does). Typing `player@arcadia.exampl` has to
    surface the account rather than 404 until the last letter.

    The caller is excluded: gifting to yourself is refused later anyway, and
    suggesting it is a dead end. Short queries return nobody rather than the
    start of a directory. The cap is small on purpose.
    """

    def __init__(self, user_repo: UserRepositoryPort):
        self._user_repo = user_repo

    async def execute(self, query: str, *, exclude_user_id: str = "") -> list[User]:
        needle = query.strip()
        if len(needle) < MIN_QUERY_LENGTH:
            return []
        return await self._user_repo.search_active(needle, limit=MAX_RESULTS, exclude_user_id=exclude_user_id)
