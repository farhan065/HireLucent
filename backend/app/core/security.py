"""Password hashing with Argon2."""

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Return a salted Argon2 hash of the password."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return True if the password matches the stored hash."""
    try:
        return _hasher.verify(password_hash, password)
    except VerificationError:
        return False