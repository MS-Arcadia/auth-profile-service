from datetime import datetime

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


class RecipientResponse(BaseModel):
    """Just enough to confirm you are sending a gift to the right person.

    The id, because that is what a gift is addressed with, and the display name, so the
    sender can see whose it is before they pay. Nothing else — not the email that was
    typed to find them, not their role, not their state. A lookup that answers more than
    the question is a directory.
    """

    user_id: str
    display_name: str
    avatar_url: str = ""


class RecipientSuggestion(BaseModel):
    """One row in the gift-box autocomplete.

    Email is here on purpose: lookup withholds it because that call confirms a person
    already named, but suggestions exist to finish an address that is still being typed.
    Without the email, `player@arcadia.exampl` cannot be picked from a list of names.
    """

    user_id: str
    display_name: str
    email: str
    avatar_url: str = ""


class AdminUserResponse(BaseModel):
    """One account as the admin screen shows it.

    The password hash is not here and must not be: this is read by a browser, and a hash that
    reaches one is a hash somebody can work on offline.
    """

    user_id: str
    # `str`, like every other response here, and deliberately not EmailStr.
    #
    # Validating an address on the way *out* means one unusable row takes down the whole
    # screen: the super admin was seeded as admin@arcadia.local before that address was
    # changed, .local is reserved by RFC 6762, and email-validator rejected it — so listing
    # the directory answered 500 and the admin saw nobody at all.
    #
    # An address is checked when it arrives, at registration. By the time it is in the
    # database the question is no longer whether it is valid: this is the screen somebody
    # opens to *find* an account like that, and refusing to display it is the opposite of
    # what the page is for.
    email: str
    display_name: str
    role: str
    state: str
    created_at: datetime


class PendingRoleRequestResponse(BaseModel):
    request_id: str
    user_id: str
    requested_role: str
    status: str
    decision_note: str | None = None
    decided_by: str | None = None
    created_at: datetime
