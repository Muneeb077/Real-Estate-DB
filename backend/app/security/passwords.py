from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# Argon2id, OWASP-recommended parameters (19 MiB memory, 2 iterations).
_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)

# A fixed hash so a login for a missing account costs the same time as a real one.
_DUMMY = _hasher.hash("timing-equaliser")

MIN_LENGTH = 10


def hash_password(password):
    return _hasher.hash(password)


def verify_password(password_hash, password):
    try:
        return _hasher.verify(password_hash or _DUMMY, password) and bool(password_hash)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash):
    return _hasher.check_needs_rehash(password_hash)


def validate_strength(password):
    """
    Returns an error message, or None when the password is acceptable.
    """
    if len(password) < MIN_LENGTH:
        return f"Password must be at least {MIN_LENGTH} characters."
    if password.lower() == password or password.upper() == password or not any(c.isdigit() for c in password):
        return "Password needs upper- and lower-case letters and a number."
    return None
