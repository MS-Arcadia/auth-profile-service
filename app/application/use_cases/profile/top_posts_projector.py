import uuid
from app.application.ports.profile_ports import ProfileRepositoryPort
from app.domain.profile.value_objects import TopPost


class TopPostsProjector:

    def __init__(self, profile_repo: ProfileRepositoryPort):
        self._profile_repo = profile_repo

    async def handle(self, event: dict) -> None:
        """event = {"user_id": ..., "post_id": ..., "feedback_score": ...}"""
        user_id = event["user_id"]
        await self._profile_repo.create_if_missing(user_id, display_name=event.get("display_name", ""))

        top_post = TopPost(
            id=str(uuid.uuid4()),
            user_id=user_id,
            post_id=event["post_id"],
            feedback_score=event["feedback_score"],
            rank=0,
        )
        await self._profile_repo.upsert_top_post(top_post)
