from fastapi import APIRouter, Depends, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.application.dto.auth_dto import (
    RegisterRequest, RegisterResponse, LoginRequest, TokenPairResponse,
    RefreshRequest, LogoutRequest,
)
from app.application.use_cases.auth.register_user import RegisterUserUseCase
from app.application.use_cases.auth.login import LoginUseCase
from app.application.use_cases.auth.refresh_token import RefreshTokenUseCase
from app.application.use_cases.auth.logout import LogoutUseCase
from app.core.dependencies import (
    get_register_user_use_case, get_login_use_case,
    get_refresh_token_use_case, get_logout_use_case,
)
from app.config import settings

router = APIRouter(prefix="/auth", tags=["Auth"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.rate_limit_register)
async def register(
    request: Request,
    body: RegisterRequest,
    use_case: RegisterUserUseCase = Depends(get_register_user_use_case),
):
    user = await use_case.execute(body.email, body.password, body.display_name)
    return RegisterResponse(user_id=user.id, email=user.email, state=user.state.value)


@router.post("/login", response_model=TokenPairResponse)
@limiter.limit(settings.rate_limit_login)
async def login(
    request: Request,
    body: LoginRequest,
    use_case: LoginUseCase = Depends(get_login_use_case),
):
    client_ip = request.client.host if request.client else "unknown"
    access_token, refresh_token = await use_case.execute(body.email, body.password, client_ip)
    return TokenPairResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh(
    body: RefreshRequest,
    use_case: RefreshTokenUseCase = Depends(get_refresh_token_use_case),
):
    access_token = await use_case.execute(body.refresh_token)
    return TokenPairResponse(access_token=access_token, refresh_token=body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: LogoutRequest,
    use_case: LogoutUseCase = Depends(get_logout_use_case),
):
    await use_case.execute(body.refresh_token)
