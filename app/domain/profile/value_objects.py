from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class OwnedGame:
    id: str
    user_id: str
    game_id: str
    hidden: bool = False
    acquired_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class OwnedItem:
    id: str
    user_id: str
    item_id: str
    game_id: str
    acquired_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TopPost:
    id: str
    user_id: str
    post_id: str
    feedback_score: int
    rank: int  # 1..5
