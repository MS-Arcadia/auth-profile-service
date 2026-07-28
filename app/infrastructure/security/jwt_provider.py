import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.application.ports.auth_ports import JwtProviderPort
from app.domain.auth.exceptions import TokenError
from app.config import settings


class JwtTokenProvider(JwtProviderPort):

    def __init__(self):
        self._secret = settings.jwt_secret
        self._algorithm = settings.jwt_algorithm
        self._access_ttl = timedelta(minutes=settings.access_token_ttl_minutes)
        self._refresh_ttl = timedelta(days=settings.refresh_token_ttl_days)

    def create_access_token(self, user_id: str, role: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id, "role": role, "type": "access",
            "iat": now, "exp": now + self._access_ttl, "jti": str(uuid.uuid4()),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def create_refresh_token(self, user_id: str) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id, "type": "refresh",
            "iat": now, "exp": now + self._refresh_ttl, "jti": str(uuid.uuid4()),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode_access_token(self, token: str) -> dict:
        return self._decode(token, expected_type="access")

    def decode_refresh_token(self, token: str) -> dict:
        return self._decode(token, expected_type="refresh")

    def _decode(self, token: str, expected_type: str) -> dict:
        try:
            claims = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except jwt.PyJWTError as exc:
            raise TokenError(f"Invalid token: {exc}") from exc

        if claims.get("type") != expected_type:
            raise TokenError(f"Expected a '{expected_type}' token.")
        return claims
