class ProfileDomainError(Exception):
    pass


class ProfileNotFoundError(ProfileDomainError):
    def __init__(self, user_id: str):
        super().__init__(f"Profile for user '{user_id}' was not found.")
        self.user_id = user_id
