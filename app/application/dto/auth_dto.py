from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=2, max_length=64)


class RegisterResponse(BaseModel):
    user_id: str
    email: str
    state: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    # OAuth2's literal, not a credential — bandit sees the field name and guesses.
    token_type: str = "bearer"  # noqa: S105


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class RequestRoleRequest(BaseModel):
    requested_role: str = Field(description="DEVELOPER or SUPPORT (or role-change request)")


class RoleRequestResponse(BaseModel):
    request_id: str
    status: str


class DecideRoleRequest(BaseModel):
    approve: bool
    note: str | None = None


class GrantRoleRequest(BaseModel):
    new_role: str


class BanRequest(BaseModel):
    reason: str | None = None


class UserSummaryResponse(BaseModel):
    user_id: str
    email: str
    display_name: str
    role: str
    state: str
