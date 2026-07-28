from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List

from app.domain.profile.value_objects import OwnedGame, OwnedItem, TopPost

MAX_TOP_POSTS = 5


@dataclass
class Profile:
    user_id: str
    display_name: str
    avatar_url: str = ""
    online: bool = False
    owned_games: List[OwnedGame] = field(default_factory=list)
    owned_items: List[OwnedItem] = field(default_factory=list)
    top_posts: List[TopPost] = field(default_factory=list)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def visible_games(self) -> List[OwnedGame]:
        return [g for g in self.owned_games if not g.hidden]

    def hide_game(self, game_id: str) -> None:
        for g in self.owned_games:
            if g.game_id == game_id:
                g.hidden = True
                return

    def unhide_game(self, game_id: str) -> None:
        for g in self.owned_games:
            if g.game_id == game_id:
                g.hidden = False
                return

    def add_owned_game(self, owned_game: OwnedGame) -> None:
        self.owned_games.append(owned_game)

    def add_owned_item(self, owned_item: OwnedItem) -> None:
        self.owned_items.append(owned_item)

    def set_presence(self, online: bool) -> None:
        self.online = online

    def upsert_top_posts(self, candidate: TopPost) -> None:
        self.top_posts = [p for p in self.top_posts if p.post_id != candidate.post_id]
        self.top_posts.append(candidate)
        self.top_posts.sort(key=lambda p: p.feedback_score, reverse=True)
        self.top_posts = self.top_posts[:MAX_TOP_POSTS]
        for i, p in enumerate(self.top_posts, start=1):
            p.rank = i
