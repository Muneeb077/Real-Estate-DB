import hmac
import secrets
import time

import pyotp

from .crypto import sha256

ISSUER = "HomeNest"


def new_secret():
    return pyotp.random_base32()


def provisioning_uri(secret, account_name):
    return pyotp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=ISSUER)


def verify(secret, code, last_step=None):
    """
    Checks a 6-digit TOTP code (±1 step of clock drift). Returns the matched
    time step, or None. Codes at or before `last_step` are rejected so a code
    cannot be replayed.
    """
    if not secret:
        return None
    totp = pyotp.TOTP(secret)
    code = str(code).strip()
    now_step = int(time.time()) // totp.interval
    for step in (now_step - 1, now_step, now_step + 1):
        if last_step is not None and step <= last_step:
            continue
        if hmac.compare_digest(totp.generate_otp(step), code):
            return step
    return None


def new_recovery_codes(n=8):
    codes = [f"{secrets.token_hex(3)}-{secrets.token_hex(3)}" for _ in range(n)]
    return codes, [sha256(c).hex() for c in codes]
