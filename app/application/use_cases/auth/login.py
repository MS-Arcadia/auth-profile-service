import asyncio

from app.application.ports.auth_ports import JwtProviderPort, PasswordHasherPort, UserRepositoryPort
from app.domain.auth.exceptions import AccountNotUsableError, InvalidCredentialsError


class LoginUseCase:
    def __init__(
        self,
        user_repo: UserRepositoryPort,
        password_hasher: PasswordHasherPort,
        jwt_provider: JwtProviderPort,
    ):
        self._user_repo = user_repo
        self._hasher = password_hasher
        self._jwt = jwt_provider

    async def execute(self, email: str, password: str, ip: str) -> tuple[str, str]:
        user = await self._user_repo.get_by_email(email.lower().strip())

        # bcrypt is deliberately slow, and slow on the event loop thread means the whole
        # process answers nothing else while one password is checked — including /livez, which
        # is how a burst of sign-ins got this service killed by its own liveness probe. The
        # hop belongs here rather than in the port: `verify_password` stays an ordinary
        # synchronous domain method, and the concurrency concern stays in the application
        # layer where the rest of the awaiting already is.
        matches = user is not None and await asyncio.to_thread(user.verify_password, password, self._hasher)
        if not matches:
            await self._user_repo.record_login_audit(user.id if user else None, ip, success=False)
            raise InvalidCredentialsError()

        if not user.can_login():
            await self._user_repo.record_login_audit(user.id, ip, success=False)
            # A distinct error, because this branch is only reachable with the correct password —
            # so it tells its owner something true and an attacker nothing they did not already
            # have. The audit entry is still recorded as a failure: the sign-in did not happen.
            raise AccountNotUsableError(user.state.value)

        await self._user_repo.record_login_audit(user.id, ip, success=True)

        access_token = self._jwt.create_access_token(user.id, user.role.value)
        refresh_token = self._jwt.create_refresh_token(user.id)
        return access_token, refresh_token
