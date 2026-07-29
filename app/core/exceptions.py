import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.domain.auth.exceptions import (
    AccountNotUsableError,
    DomainError,
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidRoleTransitionError,
    InvalidStateTransitionError,
    RoleRequestAlreadyDecidedError,
    RoleRequestNotFoundError,
    TokenError,
    UserNotFoundError,
)
from app.domain.profile.exceptions import ProfileDomainError, ProfileNotFoundError

logger = logging.getLogger(__name__)

_STATUS_MAP = {
    DuplicateEmailError: status.HTTP_409_CONFLICT,
    InvalidCredentialsError: status.HTTP_401_UNAUTHORIZED,
    # 403, not 401: the credentials were correct and the account is not usable, so
    # there is nothing to re-authenticate with and a 401 would invite a retry.
    AccountNotUsableError: status.HTTP_403_FORBIDDEN,
    TokenError: status.HTTP_401_UNAUTHORIZED,
    InvalidStateTransitionError: status.HTTP_409_CONFLICT,
    InvalidRoleTransitionError: status.HTTP_403_FORBIDDEN,
    UserNotFoundError: status.HTTP_404_NOT_FOUND,
    RoleRequestNotFoundError: status.HTTP_404_NOT_FOUND,
    RoleRequestAlreadyDecidedError: status.HTTP_409_CONFLICT,
    ProfileNotFoundError: status.HTTP_404_NOT_FOUND,
}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError):
        status_code = _STATUS_MAP.get(type(exc), status.HTTP_400_BAD_REQUEST)
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    @app.exception_handler(ProfileDomainError)
    async def handle_profile_domain_error(request: Request, exc: ProfileDomainError):
        status_code = _STATUS_MAP.get(type(exc), status.HTTP_400_BAD_REQUEST)
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error."},
        )
