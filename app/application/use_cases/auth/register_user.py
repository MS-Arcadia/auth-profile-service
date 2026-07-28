from app.domain.auth.user import User
from app.domain.auth.exceptions import DuplicateEmailError
from app.application.ports.auth_ports import UserRepositoryPort, PasswordHasherPort


class RegisterUserUseCase:

    def __init__(self, user_repo: UserRepositoryPort, password_hasher: PasswordHasherPort):
        self._user_repo = user_repo
        self._hasher = password_hasher

    async def execute(self, email: str, password: str, display_name: str) -> User:
        existing = await self._user_repo.get_by_email(email.lower().strip())
        if existing is not None:
            raise DuplicateEmailError(email)

        password_hash = self._hasher.hash(password)
        user = User.register(email=email, password_hash=password_hash, display_name=display_name)

        events = user.pull_events()
        await self._user_repo.save(user, events)
        return user
