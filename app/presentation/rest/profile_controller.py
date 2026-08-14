from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.application.dto.profile_dto import (
    OwnedGameResponse,
    OwnedItemResponse,
    ProfileResponse,
    SetAvatarRequest,
    TopPostResponse,
)
from app.application.use_cases.profile.get_profile import GetProfileUseCase
from app.application.use_cases.profile.set_avatar import SetAvatarUseCase
from app.core.dependencies import get_profile_use_case, get_set_avatar_use_case
from app.core.security_deps import CurrentUser, get_current_user, get_optional_user

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.post("/avatar", status_code=status.HTTP_204_NO_CONTENT)
async def set_avatar(
    body: SetAvatarRequest,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: SetAvatarUseCase = Depends(get_set_avatar_use_case),
):
    """Store a public media URL as this account's avatar.

    The bytes live in media-service. This service keeps the URL the same way
    catalog keeps a teaser: a string, not the file.
    """
    await use_case.execute(current_user.user_id, body.avatar_url)


@router.get("/{user_id}", response_model=ProfileResponse)
async def get_profile(
    user_id: str,
    current_user: CurrentUser | None = Depends(get_optional_user),
    use_case: GetProfileUseCase = Depends(get_profile_use_case),
):
    """One profile, as its owner or as a visitor.

    The difference is the hidden games. A visitor sees the shelf its owner chose to show;
    the owner sees all of it, each game carrying whether it is hidden.

    That distinction is the whole reason `hidden` is in the response, and it was missing:
    every caller got `visible_games()`, so the flag was always false and a game that had
    been hidden vanished from the only screen that could have unhidden it. The unhide route
    and the domain method behind it both existed and were unreachable.
    """
    profile = await use_case.execute(user_id)
    is_owner = current_user is not None and current_user.user_id == user_id
    games = profile.owned_games if is_owner else profile.visible_games()
    return ProfileResponse(
        user_id=profile.user_id,
        display_name=profile.display_name,
        avatar_url=profile.avatar_url,
        online=profile.online,
        owned_games=[OwnedGameResponse(game_id=g.game_id, hidden=g.hidden) for g in games],
        owned_items=[OwnedItemResponse(item_id=i.item_id, game_id=i.game_id) for i in profile.owned_items],
        top_posts=[
            TopPostResponse(post_id=p.post_id, feedback_score=p.feedback_score, rank=p.rank) for p in profile.top_posts
        ],
    )
