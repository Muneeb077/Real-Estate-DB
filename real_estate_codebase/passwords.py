from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()  # Argon2id with a random per-password salt


def hash_password(password):
    return _hasher.hash(password)


def verify_password(password_hash, password):
    """
    Returns True when `password` matches the stored Argon2id hash.
    """
    if not password_hash:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash):
    return _hasher.check_needs_rehash(password_hash)
