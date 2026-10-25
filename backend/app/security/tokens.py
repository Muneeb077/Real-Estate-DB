"""
Session tokens.

- Access token: short-lived JWT (HS256) in an httpOnly cookie.
- Refresh token: random 256-bit secret in an httpOnly cookie scoped to /api/v1/auth.
  Only its SHA-256 hash is stored. Every refresh rotates it; presenting an
  already-rotated token is treated as theft and revokes the whole token family.
- CSRF: double-submit token. A readable cookie whose value must be echoed in
  the X-CSRF-Token header on every state-changing request.
"""
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from flask import current_app
from ulid import ULID

from .. import db
from .crypto import sha256

ACCESS_COOKIE = "hn_access"
REFRESH_COOKIE = "hn_refresh"
CSRF_COOKIE = "hn_csrf"
REFRESH_PATH = "/api/v1/auth"


def _now():
    return datetime.now(timezone.utc)


def issue_access_token(user, mfa=False):
    now = _now()
    payload = {
        "sub": str(user["id"]),
        "pid": user["public_id"],
        "mfa": bool(mfa),
        "iat": now,
        "exp": now + timedelta(seconds=current_app.config["JWT_ACCESS_TTL"]),
        "jti": secrets.token_hex(8),
        "typ": "access",
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def issue_purpose_token(user_id, purpose, ttl_seconds):
    """
    Short-lived signed token for a single step (e.g. the MFA challenge after a correct password).
    """
    now = _now()
    payload = {"sub": str(user_id), "typ": purpose, "iat": now, "exp": now + timedelta(seconds=ttl_seconds)}
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def decode(token, expected_type="access"):
    try:
        payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return payload if payload.get("typ") == expected_type else None


def issue_refresh_token(user_id, mfa, user_agent=None, ip=None, family_id=None, conn=None):
    token = secrets.token_urlsafe(32)
    db.execute(
        """INSERT INTO refresh_tokens (user_id, family_id, token_hash, mfa, user_agent, ip, expires_at)
           VALUES (:u, :f, :h, :m, :ua, :ip, :exp)""",
        {"u": user_id, "f": family_id or str(ULID()), "h": sha256(token), "m": mfa,
         "ua": (user_agent or "")[:255], "ip": ip,
         "exp": _now() + timedelta(days=current_app.config["REFRESH_TTL_DAYS"])},
        conn=conn,
    )
    return token


def rotate_refresh_token(token, user_agent=None, ip=None):
    """
    Returns (user_id, mfa, new_token) or None. Reuse of a rotated token revokes the family.
    """
    with db.transaction() as conn:
        row = db.one("SELECT * FROM refresh_tokens WHERE token_hash = :h FOR UPDATE",
                     {"h": sha256(token)}, conn=conn)
        if not row:
            return None
        if row["revoked_at"] is not None:
            db.execute("UPDATE refresh_tokens SET revoked_at = NOW() WHERE family_id = :f AND revoked_at IS NULL",
                       {"f": row["family_id"]}, conn=conn)
            return None
        if datetime.fromisoformat(row["expires_at"]).replace(tzinfo=timezone.utc) < _now():
            return None
        db.execute("UPDATE refresh_tokens SET revoked_at = NOW() WHERE id = :id", {"id": row["id"]}, conn=conn)
        new = issue_refresh_token(row["user_id"], bool(row["mfa"]), user_agent, ip, row["family_id"], conn=conn)
        return row["user_id"], bool(row["mfa"]), new


def revoke_refresh_token(token):
    db.execute("""UPDATE refresh_tokens r JOIN refresh_tokens t ON t.family_id = r.family_id
                  SET r.revoked_at = NOW() WHERE t.token_hash = :h AND r.revoked_at IS NULL""",
               {"h": sha256(token)})


def revoke_all_for_user(user_id, conn=None):
    db.execute("UPDATE refresh_tokens SET revoked_at = NOW() WHERE user_id = :u AND revoked_at IS NULL",
               {"u": user_id}, conn=conn)


def set_auth_cookies(response, access, refresh=None):
    cfg = current_app.config
    secure = cfg["COOKIE_SECURE"]
    response.set_cookie(ACCESS_COOKIE, access, max_age=cfg["JWT_ACCESS_TTL"], httponly=True,
                        secure=secure, samesite="Lax", path="/")
    if refresh:
        response.set_cookie(REFRESH_COOKIE, refresh, max_age=cfg["REFRESH_TTL_DAYS"] * 86400, httponly=True,
                            secure=secure, samesite="Strict", path=REFRESH_PATH)
    response.set_cookie(CSRF_COOKIE, secrets.token_urlsafe(24), max_age=cfg["REFRESH_TTL_DAYS"] * 86400,
                        httponly=False, secure=secure, samesite="Lax", path="/")
    return response


def clear_auth_cookies(response):
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)
    response.delete_cookie(CSRF_COOKIE, path="/")
    return response
