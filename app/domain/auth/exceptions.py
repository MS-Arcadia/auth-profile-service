class DomainError(Exception):
    """Base class for all domain-layer errors. Never leaks infrastructure details."""


class InvalidStateTransitionError(DomainError):
    def __init__(self, current_state: str, action: str):
        super().__init__(f"Cannot perform '{action}' while account is in state '{current_state}'.")
        self.current_state = current_state
        self.action = action


class InvalidRoleTransitionError(DomainError):
    def __init__(self, message: str):
        super().__init__(message)


class DuplicateEmailError(DomainError):
    def __init__(self, email: str):
        super().__init__(f"Email '{email}' is already registered.")
        self.email = email


class InvalidCredentialsError(DomainError):
    def __init__(self):
        super().__init__("Invalid email or password.")


class UserNotFoundError(DomainError):
    def __init__(self, user_id: str):
        super().__init__(f"User '{user_id}' was not found.")
        self.user_id = user_id


class RoleRequestNotFoundError(DomainError):
    def __init__(self, request_id: str):
        super().__init__(f"Role request '{request_id}' was not found.")


class RoleRequestAlreadyDecidedError(DomainError):
    def __init__(self, request_id: str):
        super().__init__(f"Role request '{request_id}' has already been decided.")


class TokenError(DomainError):
    def __init__(self, message: str = "Invalid or expired token."):
        super().__init__(message)
