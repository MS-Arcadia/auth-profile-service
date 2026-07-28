from app.domain.auth.enums import Role
from app.domain.auth.exceptions import InvalidRoleTransitionError

SELF_REQUESTABLE_ROLES = {Role.DEVELOPER, Role.SUPPORT}


class RolePolicy:
    @staticmethod
    def can_request(current_role: Role, requested_role: Role) -> bool:
        if requested_role == current_role:
            return False
        return requested_role in SELF_REQUESTABLE_ROLES or current_role != Role.BASIC_USER

    @staticmethod
    def assert_can_grant(granter_role: Role, target_role: Role) -> None:
        if granter_role != Role.ADMIN:
            raise InvalidRoleTransitionError("Only ADMIN can directly grant/change a user's role.")

    @staticmethod
    def assert_can_decide_role_request(decider_role: Role) -> None:
        if decider_role not in (Role.SUPPORT, Role.ADMIN):
            raise InvalidRoleTransitionError(
                "Only SUPPORT or ADMIN can approve/reject role requests."
            )

    @staticmethod
    def assert_can_ban(actor_role: Role) -> None:
        if actor_role not in (Role.SUPPORT, Role.ADMIN):
            raise InvalidRoleTransitionError("Only SUPPORT or ADMIN can ban/unban users.")

    @staticmethod
    def assert_can_approve_registration(actor_role: Role) -> None:
        if actor_role not in (Role.SUPPORT, Role.ADMIN):
            raise InvalidRoleTransitionError(
                "Only SUPPORT or ADMIN can approve/reject registrations."
            )
