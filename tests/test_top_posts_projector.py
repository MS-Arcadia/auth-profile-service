import pytest

from app.application.ports.profile_ports import ProfileRepositoryPort
from app.application.use_cases.profile.top_posts_projector import TopPostsProjector
from app.domain.profile.profile import Profile
from app.domain.profile.value_objects import TopPost


class FakeProfileRepository(ProfileRepositoryPort):
    """The minimum a projector needs: a profile store keyed by user id and a top-posts table keyed by
    (user_id, post_id), mirroring the real repository's upsert semantics closely enough to test against."""

    def __init__(self) -> None:
        self.profiles: dict[str, Profile] = {}
        self.top_posts: dict[tuple[str, str], TopPost] = {}

    async def get_by_user_id(self, user_id: str) -> Profile | None:
        return self.profiles.get(user_id)

    async def save(self, profile: Profile) -> None:
        self.profiles[profile.user_id] = profile

    async def create_if_missing(self, user_id: str, display_name: str) -> Profile:
        if user_id not in self.profiles:
            self.profiles[user_id] = Profile(user_id=user_id, display_name=display_name)
        return self.profiles[user_id]

    async def add_owned_game(self, owned_game: object) -> None:
        raise NotImplementedError

    async def owns_game(self, user_id: str, game_id: str) -> bool:
        raise NotImplementedError

    async def remove_owned_game(self, user_id: str, game_id: str) -> None:
        raise NotImplementedError

    async def add_owned_item(self, owned_item: object) -> None:
        raise NotImplementedError

    async def upsert_top_post(self, top_post: TopPost) -> None:
        self.top_posts[(top_post.user_id, top_post.post_id)] = top_post

    async def set_hidden(self, user_id: str, game_id: str, hidden: bool) -> None:
        raise NotImplementedError


@pytest.fixture
def repo() -> FakeProfileRepository:
    return FakeProfileRepository()


@pytest.mark.asyncio
async def test_the_top_post_is_credited_to_the_authors_profile_not_the_reactors(
    repo: FakeProfileRepository,
) -> None:
    """This is exactly the bug: `PostReacted` carries the reactor as `user_id` and the post's author as
    `author_id`. Crediting the reaction to `user_id`, as the projector used to, would update the *reactor's*
    top-posts list for a post they did not even write."""
    event = {
        "post_id": "post-1",
        "user_id": "reactor-1",
        "author_id": "author-1",
        "emoji": "🔥",
        "previous_emoji": None,
        "feedback_score": 3,
    }
    await TopPostsProjector(repo).handle(event)

    assert repo.profiles.keys() == {"author-1"}
    assert ("author-1", "post-1") in repo.top_posts
    assert ("reactor-1", "post-1") not in repo.top_posts
    stored = repo.top_posts[("author-1", "post-1")]
    assert stored.feedback_score == 3
    assert stored.post_id == "post-1"


@pytest.mark.asyncio
async def test_a_second_reaction_updates_the_same_top_post_rather_than_duplicating_it(
    repo: FakeProfileRepository,
) -> None:
    base_event = {
        "post_id": "post-1",
        "user_id": "reactor-1",
        "author_id": "author-1",
        "emoji": "🔥",
        "previous_emoji": None,
        "feedback_score": 1,
    }
    await TopPostsProjector(repo).handle(base_event)
    await TopPostsProjector(repo).handle(
        {**base_event, "user_id": "reactor-2", "feedback_score": 2}
    )

    assert len(repo.top_posts) == 1
    assert repo.top_posts[("author-1", "post-1")].feedback_score == 2
