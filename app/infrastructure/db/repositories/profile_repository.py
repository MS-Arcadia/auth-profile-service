from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.application.ports.profile_ports import ProfileRepositoryPort
from app.domain.profile.profile import Profile
from app.domain.profile.value_objects import OwnedGame, OwnedItem, TopPost
from app.infrastructure.db.models.profile_models import (
    ProfileModel, OwnedGameModel, OwnedItemModel, TopPostModel,
)


def _to_domain_profile(row: ProfileModel, games, items, posts) -> Profile:
    return Profile(
        user_id=row.user_id,
        display_name=row.display_name,
        avatar_url=row.avatar_url,
        online=row.online,
        owned_games=[OwnedGame(id=g.id, user_id=g.user_id, game_id=g.game_id,
                                hidden=g.hidden, acquired_at=g.acquired_at) for g in games],
        owned_items=[OwnedItem(id=i.id, user_id=i.user_id, item_id=i.item_id,
                                game_id=i.game_id, acquired_at=i.acquired_at) for i in items],
        top_posts=[TopPost(id=p.id, user_id=p.user_id, post_id=p.post_id,
                            feedback_score=p.feedback_score, rank=p.rank) for p in posts],
        updated_at=row.updated_at,
    )


class SqlAlchemyProfileRepository(ProfileRepositoryPort):

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_user_id(self, user_id: str) -> Optional[Profile]:
        row = await self._session.get(ProfileModel, user_id)
        if row is None:
            return None
        games = (await self._session.execute(
            select(OwnedGameModel).where(OwnedGameModel.user_id == user_id))).scalars().all()
        items = (await self._session.execute(
            select(OwnedItemModel).where(OwnedItemModel.user_id == user_id))).scalars().all()
        posts = (await self._session.execute(
            select(TopPostModel).where(TopPostModel.user_id == user_id).order_by(TopPostModel.rank))
        ).scalars().all()
        return _to_domain_profile(row, games, items, posts)

    async def save(self, profile: Profile) -> None:
        row = await self._session.get(ProfileModel, profile.user_id)
        if row is None:
            row = ProfileModel(user_id=profile.user_id)
            self._session.add(row)
        row.display_name = profile.display_name
        row.avatar_url = profile.avatar_url
        row.online = profile.online
        await self._session.commit()

    async def create_if_missing(self, user_id: str, display_name: str) -> Profile:
        stmt = pg_insert(ProfileModel).values(
            user_id=user_id, display_name=display_name, avatar_url="", online=False,
        ).on_conflict_do_nothing(index_elements=["user_id"])
        await self._session.execute(stmt)
        await self._session.commit()
        return await self.get_by_user_id(user_id)

    async def add_owned_game(self, owned_game: OwnedGame) -> None:
        self._session.add(OwnedGameModel(
            id=owned_game.id, user_id=owned_game.user_id, game_id=owned_game.game_id,
            hidden=owned_game.hidden, acquired_at=owned_game.acquired_at,
        ))
        await self._session.commit()

    async def add_owned_item(self, owned_item: OwnedItem) -> None:
        self._session.add(OwnedItemModel(
            id=owned_item.id, user_id=owned_item.user_id, item_id=owned_item.item_id,
            game_id=owned_item.game_id, acquired_at=owned_item.acquired_at,
        ))
        await self._session.commit()

    async def upsert_top_post(self, top_post: TopPost) -> None:
        existing = (await self._session.execute(
            select(TopPostModel).where(
                TopPostModel.user_id == top_post.user_id, TopPostModel.post_id == top_post.post_id
            )
        )).scalar_one_or_none()

        if existing:
            existing.feedback_score = top_post.feedback_score
        else:
            self._session.add(TopPostModel(
                id=top_post.id, user_id=top_post.user_id, post_id=top_post.post_id,
                feedback_score=top_post.feedback_score, rank=0,
            ))
        await self._session.commit()

        all_posts = (await self._session.execute(
            select(TopPostModel).where(TopPostModel.user_id == top_post.user_id)
            .order_by(TopPostModel.feedback_score.desc())
        )).scalars().all()

        for idx, post_row in enumerate(all_posts, start=1):
            if idx <= 5:
                post_row.rank = idx
            else:
                await self._session.delete(post_row)
        await self._session.commit()

    async def set_hidden(self, user_id: str, game_id: str, hidden: bool) -> None:
        row = (await self._session.execute(
            select(OwnedGameModel).where(
                OwnedGameModel.user_id == user_id, OwnedGameModel.game_id == game_id
            )
        )).scalar_one_or_none()
        if row:
            row.hidden = hidden
            await self._session.commit()
