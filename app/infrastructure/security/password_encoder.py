from passlib.context import CryptContext

from app.application.ports.auth_ports import PasswordHasherPort

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class BcryptPasswordEncoder(PasswordHasherPort):
    def hash(self, plain_password: str) -> str:
        return _pwd_context.hash(plain_password)

    def verify(self, plain_password: str, password_hash: str) -> bool:
        return _pwd_context.verify(plain_password, password_hash)
