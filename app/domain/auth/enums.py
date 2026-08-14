"""The auth domain's closed sets.

`StrEnum` rather than `(str, Enum)`, matching the other Python services on this platform. The
difference that matters is interpolation: `f"{Role.ADMIN}"` is `"Role.ADMIN"` with the mixin and
`"ADMIN"` with StrEnum. Every site here passes `.value` explicitly, so the change is invisible to
this code — it removes the trap for the next person who does not.

The database stores these through `SAEnum`, which keys on the member *name*, so nothing about the
stored representation moves either.
"""

from enum import StrEnum


class Role(StrEnum):
    """Requirement 1.1's four roles. A user has exactly one."""

    BASIC_USER = "BASIC_USER"
    DEVELOPER = "DEVELOPER"
    SUPPORT = "SUPPORT"
    ADMIN = "ADMIN"


class UserState(StrEnum):
    """
    Account state machine:
        ACTIVE   -> BANNED
        BANNED   -> ACTIVE
        PENDING  -> ACTIVE | REJECTED  (leftover accounts; registration starts ACTIVE)
    """

    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    BANNED = "BANNED"


class RoleRequestStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
