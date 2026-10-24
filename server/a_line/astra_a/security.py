from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError


class ArgonPasswords:
    def __init__(self):
        self.hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
        self.dummy = self.hasher.hash("NonAccountTimingOnly123!")

    def hash(self, password: str) -> str:
        return self.hasher.hash(password)

    def verify(self, password: str, encoded: str | None) -> bool:
        try:
            result = self.hasher.verify(encoded or self.dummy, password)
            return bool(encoded and result)
        except (VerificationError, InvalidHashError):
            return False
