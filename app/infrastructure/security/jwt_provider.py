"""The platform's token format.

This is a contract with five other services, and none of them can be changed by this file. Every
claim below is there because something else reads it:

* ``typ`` — **not** ``type``. Every verifier on the platform reads `typ`, and an absent one used
  to be treated as "fine", which meant this service's refresh tokens were accepted as access
  tokens on every endpoint — a seven-day credential carrying a full role. Spelling it correctly
  is half the fix; the other half was making those verifiers strict.
* ``iss`` and ``aud`` — required. Without them every service answers 401, which is exactly what
  this service did before: five out of five.
* ``scopes`` — read by the media service for `media:read`, and by whatever grows a scope next.
  Always present, even when empty, so a consumer never has to tell "no scopes" from "an older
  token".
* ``role`` — one of the four roles from requirement 1.1, verbatim.

The e2e suite in `infra/test/e2e/arcadia.py` mints tokens in exactly this shape. If the two ever
disagree, that suite is what says so.
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.application.ports.auth_ports import JwtProviderPort
from app.config import settings
from app.domain.auth.exceptions import TokenError

# The claim name the whole platform uses, as a constant so the two places that touch it cannot
# drift apart.
TOKEN_TYPE_CLAIM = "typ"
ACCESS = "access"
REFRESH = "refresh"


class JwtTokenProvider(JwtProviderPort):
    def __init__(self):
        self._secret = settings.jwt_secret
        self._algorithm = settings.jwt_algorithm
        self._issuer = settings.jwt_issuer
        self._audience = settings.jwt_audience
        self._access_ttl = timedelta(minutes=settings.access_token_ttl_minutes)
        self._refresh_ttl = timedelta(days=settings.refresh_token_ttl_days)

    def create_access_token(self, user_id: str, role: str, scopes: list[str] | None = None) -> str:
        return self._sign(
            {
                "sub": user_id,
                "role": role,
                "scopes": scopes or [],
                TOKEN_TYPE_CLAIM: ACCESS,
            },
            self._access_ttl,
        )

    def create_refresh_token(self, user_id: str) -> str:
        """Deliberately carries no role.

        A refresh token is only ever presented to `/v1/auth/refresh`, which looks the user up and
        reads their *current* role. Putting a role in here would freeze it for the token's whole
        seven days, so a user demoted from ADMIN would keep administering the platform until it
        expired.
        """
        return self._sign({"sub": user_id, TOKEN_TYPE_CLAIM: REFRESH}, self._refresh_ttl)

    def _sign(self, claims: dict, ttl: timedelta) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            **claims,
            "iss": self._issuer,
            "aud": self._audience,
            "iat": now,
            "nbf": now,
            "exp": now + ttl,
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode_access_token(self, token: str) -> dict:
        return self._decode(token, expected_type=ACCESS)

    def decode_refresh_token(self, token: str) -> dict:
        return self._decode(token, expected_type=REFRESH)

    def _decode(self, token: str, expected_type: str) -> dict:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                # Verified, not merely present. PyJWT only checks these when told what to expect,
                # so omitting them would accept a correctly-signed token minted for a different
                # audience entirely.
                issuer=self._issuer,
                audience=self._audience,
            )
        except jwt.PyJWTError as exc:
            raise TokenError(f"Invalid token: {exc}") from exc

        # Strict, unlike the platform verifiers used to be: a token that does not say what it is
        # gets refused rather than assumed to be an access token.
        if claims.get(TOKEN_TYPE_CLAIM) != expected_type:
            raise TokenError(f"Expected a '{expected_type}' token.")
        return claims
