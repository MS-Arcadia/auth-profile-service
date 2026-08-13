import asyncio

from app.application.ports.auth_ports import PasswordHasherPort, UserRepositoryPort
from app.domain.auth.exceptions import DuplicateEmailError
from app.domain.auth.user import User


class RegisterUserUseCase:
    def __init__(self, user_repo: UserRepositoryPort, password_hasher: PasswordHasherPort):
        self._user_repo = user_repo
        self._hasher = password_hasher

    async def execute(self, email: str, password: str, display_name: str) -> User:
        existing = await self._user_repo.get_by_email(email.lower().strip())
        if existing is not None:
            raise DuplicateEmailError(email)

        # Off the event loop, for the same reason as the sign-in path: hashing is the most
        # expensive thing this service does and it must not stop the process answering.
        password_hash = await asyncio.to_thread(self._hasher.hash, password)
        user = User.register(email=email, password_hash=password_hash, display_name=display_name)

        events = user.pull_events()
        await self._user_repo.save(user, events)
        return user
