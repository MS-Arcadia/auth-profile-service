from fastapi import APIRouter, Depends, status

from app.application.dto.profile_dto import HideGameRequest
from app.application.use_cases.profile.hide_game import HideGameUseCase
from app.core.dependencies import get_hide_game_use_case
from app.core.security_deps import CurrentUser, get_current_user

router = APIRouter(prefix="/profile/library", tags=["Library"])


@router.post("/hide", status_code=status.HTTP_204_NO_CONTENT)
async def hide_game(
    body: HideGameRequest,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: HideGameUseCase = Depends(get_hide_game_use_case),
):
    await use_case.execute(current_user.user_id, body.game_id, hidden=True)


@router.post("/unhide", status_code=status.HTTP_204_NO_CONTENT)
async def unhide_game(
    body: HideGameRequest,
    current_user: CurrentUser = Depends(get_current_user),
    use_case: HideGameUseCase = Depends(get_hide_game_use_case),
):
    await use_case.execute(current_user.user_id, body.game_id, hidden=False)
