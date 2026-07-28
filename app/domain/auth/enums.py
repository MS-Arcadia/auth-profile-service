from enum import Enum


class Role(str, Enum):
    BASIC_USER = "BASIC_USER"
    DEVELOPER = "DEVELOPER"
    SUPPORT = "SUPPORT"
    ADMIN = "ADMIN"


class UserState(str, Enum):
    """
    Account state machine:
        PENDING  -> ACTIVE
        PENDING  -> REJECTED
        ACTIVE   -> BANNED
        BANNED   -> ACTIVE
    """
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    BANNED = "BANNED"


class RoleRequestStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
