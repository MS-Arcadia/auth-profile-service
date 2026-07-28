from app.domain.auth.exceptions import InvalidCredentialsError
from app.application.ports.auth_ports import UserRepositoryPort, PasswordHasherPort, JwtProviderPort


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

        if user is None or not user.verify_password(password, self._hasher):
            await self._user_repo.record_login_audit(user.id if user else None, ip, success=False)
            raise InvalidCredentialsError()

        if not user.can_login():
            await self._user_repo.record_login_audit(user.id, ip, success=False)
            raise InvalidCredentialsError()

        await self._user_repo.record_login_audit(user.id, ip, success=True)

        access_token = self._jwt.create_access_token(user.id, user.role.value)
        refresh_token = self._jwt.create_refresh_token(user.id)
        return access_token, refresh_token
