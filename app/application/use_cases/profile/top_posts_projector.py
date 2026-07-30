import uuid

from app.application.ports.profile_ports import ProfileRepositoryPort
from app.domain.profile.value_objects import TopPost


class TopPostsProjector:
    def __init__(self, profile_repo: ProfileRepositoryPort):
        self._profile_repo = profile_repo

    async def handle(self, event: dict) -> None:
        """event = {"post_id": ..., "author_id": ..., "feedback_score": ..., "user_id": ..., "emoji": ...}

        The top-posts list belongs to the post's author, not to whoever reacted: `author_id` is the profile
        to update. `user_id` is the reactor and is not read here — Community keeps it in the payload only
        for its own idempotency and audit trail.
        """
        author_id = event["author_id"]
        await self._profile_repo.create_if_missing(
            author_id, display_name=event.get("display_name", "")
        )

        top_post = TopPost(
            id=str(uuid.uuid4()),
            user_id=author_id,
            post_id=event["post_id"],
            feedback_score=event["feedback_score"],
            rank=0,
        )
        await self._profile_repo.upsert_top_post(top_post)
