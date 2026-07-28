from app.domain.profile.profile import MAX_TOP_POSTS, Profile
from app.domain.profile.value_objects import OwnedGame, TopPost


def _make_post(post_id: str, score: int) -> TopPost:
    return TopPost(id=post_id, user_id="u1", post_id=post_id, feedback_score=score, rank=0)


def test_top_posts_keeps_only_top_5():
    profile = Profile(user_id="u1", display_name="Alice")
    for i in range(10):
        profile.upsert_top_posts(_make_post(f"post-{i}", score=i))

    assert len(profile.top_posts) == MAX_TOP_POSTS
    scores = sorted((p.feedback_score for p in profile.top_posts), reverse=True)
    assert scores == [9, 8, 7, 6, 5]


def test_hide_game_removes_from_visible_but_not_from_storage():
    profile = Profile(user_id="u1", display_name="Alice")
    profile.add_owned_game(OwnedGame(id="1", user_id="u1", game_id="game-1"))
    profile.hide_game("game-1")

    assert profile.visible_games() == []
    assert len(profile.owned_games) == 1
    assert profile.owned_games[0].hidden is True
