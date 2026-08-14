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


class AccountNotUsableError(DomainError):
    """The password was right and the account still cannot be used.

    Distinct from InvalidCredentialsError on purpose, and it leaks nothing: this is only ever
    raised *after* the password has been verified, so only the account's rightful owner can see
    it. Collapsing it into "invalid email or password" tells somebody waiting for Support to
    approve their registration that they have forgotten their password — which is the one thing
    they can be certain is untrue, and the one message that guarantees a support ticket.
    """

    def __init__(self, state: str):
        messages = {
            "PENDING": "This registration is waiting for a Support decision.",
            "REJECTED": "This registration was rejected.",
            "BANNED": "This account is banned. Contact support.",
        }
        super().__init__(messages.get(state, f"This account is {state} and cannot sign in."))
        self.state = state


class UserNotFoundError(DomainError):
    def __init__(self, user_id: str):
        super().__init__(f"User '{user_id}' was not found.")
        self.user_id = user_id


class RecipientNotFoundError(DomainError):
    """Nobody on this platform answers to what was typed."""

    def __init__(self, query: str):
        super().__init__(f"No active account matches '{query}'.")
        self.query = query


class RecipientNotUniqueError(DomainError):
    """Two people share that display name.

    Reported rather than resolved to the first match: picking one is how a gift reaches a
    stranger who happens to share a name with the intended recipient.
    """

    def __init__(self, query: str, count: int):
        super().__init__(f"{count} accounts are called '{query}'. Use their email address instead.")
        self.query = query
        self.count = count


class RoleRequestNotFoundError(DomainError):
    def __init__(self, request_id: str):
        super().__init__(f"Role request '{request_id}' was not found.")


class RoleRequestAlreadyDecidedError(DomainError):
    def __init__(self, request_id: str):
        super().__init__(f"Role request '{request_id}' has already been decided.")


class TokenError(DomainError):
    def __init__(self, message: str = "Invalid or expired token."):
        super().__init__(message)
