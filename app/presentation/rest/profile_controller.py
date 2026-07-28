from fastapi import APIRouter, Depends

from app.application.dto.profile_dto import (
    ProfileResponse, OwnedGameResponse, OwnedItemResponse, TopPostResponse,
)
from app.application.use_cases.profile.get_profile import GetProfileUseCase
from app.core.security_deps import get_current_user, CurrentUser
from app.core.dependencies import get_profile_use_case

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("/{user_id}", response_model=ProfileResponse)
async def get_profile(
    user_id: str,
    _current_user: CurrentUser = Depends(get_current_user),
    use_case: GetProfileUseCase = Depends(get_profile_use_case),
):
    profile = await use_case.execute(user_id)
    return ProfileResponse(
        user_id=profile.user_id,
        display_name=profile.display_name,
        avatar_url=profile.avatar_url,
        online=profile.online,
        owned_games=[
            OwnedGameResponse(game_id=g.game_id, hidden=g.hidden) for g in profile.visible_games()
        ],
        owned_items=[
            OwnedItemResponse(item_id=i.item_id, game_id=i.game_id) for i in profile.owned_items
        ],
        top_posts=[
            TopPostResponse(post_id=p.post_id, feedback_score=p.feedback_score, rank=p.rank)
            for p in profile.top_posts
        ],
    )
