"""The admin directory has to be able to show an account it would refuse to create.

`AdminUserResponse.email` was `EmailStr`, which validates on the way out. The super admin
was seeded as `admin@arcadia.local` before that address was changed, `.local` is reserved by
RFC 6762, and so listing the directory answered 500 — the admin screen showed nobody, and
the one row that broke it was the one somebody would open the screen to fix.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.application.dto.auth_dto import AdminUserResponse, RegisterRequest


def build(email: str) -> AdminUserResponse:
    return AdminUserResponse(
        user_id="u-1",
        email=email,
        display_name="Someone",
        role="ADMIN",
        state="ACTIVE",
        created_at=datetime.now(UTC),
    )


@pytest.mark.parametrize(
    "email",
    [
        "admin@arcadia.local",  # the address that actually took the screen down
        "admin@arcadia.example",
        "someone@example.com",
        "",  # a row with nothing in it is still a row an admin may need to act on
    ],
)
def test_any_stored_address_can_be_listed(email: str):
    assert build(email).email == email


def test_registration_still_refuses_an_unusable_address():
    """Validation belongs where the address arrives, and it is still there."""
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="admin@arcadia.local",
            password="a-long-enough-password",
            display_name="Someone",
        )


def test_the_password_hash_is_not_in_the_response():
    """This is read by a browser, and a hash that reaches one is a hash somebody can work
    on offline."""
    assert "password" not in AdminUserResponse.model_fields
    assert "password_hash" not in AdminUserResponse.model_fields
