from pydantic import BaseModel
from typing import List


class OwnedGameResponse(BaseModel):
    game_id: str
    hidden: bool


class OwnedItemResponse(BaseModel):
    item_id: str
    game_id: str


class TopPostResponse(BaseModel):
    post_id: str
    feedback_score: int
    rank: int


class ProfileResponse(BaseModel):
    user_id: str
    display_name: str
    avatar_url: str
    online: bool
    owned_games: List[OwnedGameResponse]
    owned_items: List[OwnedItemResponse]
    top_posts: List[TopPostResponse]


class HideGameRequest(BaseModel):
    game_id: str
