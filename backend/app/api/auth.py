"""
Authentication: signup, login with lockout, rotating refresh tokens,
email verification, password reset, sessions.
"""
import secrets
from datetime import timedelta

from flask import Blueprint, current_app, g, jsonify, make_response, request
from pydantic import EmailStr, Field
from ulid import ULID

from .. import db
from ..errors import ApiError
from ..extensions import limiter
from ..security import crypto, tokens
from ..security.passwords import hash_password, needs_rehash, validate_strength, verify_password
from ..security.rbac import load_user, login_required
from ..tasks import enqueue, send_email_job
from ..users import email_hash, get_email, me_payload
from .common import Strict, body

bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")

LOCKOUT_FAILURES = 5
LOCKOUT_WINDOW_MIN = 15
VERIFY_TTL = timedelta(hours=24)
RESET_TTL = timedelta(minutes=30)


class SignupIn(Strict):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=2, max_length=120)


class LoginIn(Strict):
    email: EmailStr
    password: str = Field(max_length=200)


class TokenIn(Strict):
    token: str = Field(max_length=200)


class ForgotIn(Strict):
    email: EmailStr


class ResetIn(Strict):
    token: str = Field(max_length=200)
    password: str = Field(max_length=200)


class ChangePasswordIn(Strict):
    current_password: str = Field(max_length=200)
    new_password: str = Field(max_length=200)


def _client_ip():
    # behind Nginx the real client IP arrives in X-Forwarded-For (ProxyFix in wsgi)
    return request.remote_addr


def _start_session(user_id, status=200):
    user = load_user(user_id)
    access = tokens.issue_access_token(user)
    refresh = tokens.issue_refresh_token(user_id, request.headers.get("User-Agent"), _client_ip())
    resp = make_response(jsonify(me_payload(user)), status)
    return tokens.set_auth_cookies(resp, access, refresh)


def _issue_one_time_token(user_id, purpose, ttl, conn=None):
    token = secrets.token_urlsafe(32)
    db.execute(
        """INSERT INTO auth_tokens (user_id, purpose, token_hash, expires_at)
           VALUES (:u, :p, :h, NOW() + INTERVAL :s SECOND)""",
        {"u": user_id, "p": purpose, "h": crypto.sha256(token), "s": int(ttl.total_seconds())},
        conn=conn,
    )
    return token


def _consume_one_time_token(token, purpose, conn):
    row = db.one(
        """SELECT id, user_id FROM auth_tokens
           WHERE token_hash = :h AND purpose = :p AND used_at IS NULL AND expires_at > NOW()
           FOR UPDATE""",
        {"h": crypto.sha256(token), "p": purpose}, conn=conn)
    if not row:
        raise ApiError(400, "invalid_token", "This link is invalid or has expired.")
    db.execute("UPDATE auth_tokens SET used_at = NOW() WHERE id = :id", {"id": row["id"]}, conn=conn)
    return row["user_id"]


def _send_verification(user_id, email):
    token = _issue_one_time_token(user_id, "verify_email", VERIFY_TTL)
    link = f"{current_app.config['FRONTEND_URL']}/verify-email?token={token}"
    enqueue(send_email_job, email, "Verify your HomeNest email",
            f"Welcome to HomeNest!\n\nConfirm your email address:\n{link}\n\nThe link expires in 24 hours.")


@bp.get("/csrf")
def csrf():
    resp = make_response(jsonify(ok=True))
    if not request.cookies.get(tokens.CSRF_COOKIE):
        resp.set_cookie(tokens.CSRF_COOKIE, secrets.token_urlsafe(24), httponly=False,
                        secure=current_app.config["COOKIE_SECURE"], samesite="Lax", path="/")
    return resp


@bp.post("/signup")
@limiter.limit("5 per minute; 30 per hour")
def signup():
    data = body(SignupIn)
    if problem := validate_strength(data.password):
        raise ApiError(422, "weak_password", problem)
    email = data.email.strip().lower()
    with db.transaction() as conn:
        if db.one("SELECT 1 FROM users WHERE email_hash = :h", {"h": email_hash(email)}, conn=conn):
            raise ApiError(409, "email_taken", "An account with this email already exists.")
        _, uid = db.execute(
            """INSERT INTO users (public_id, email_enc, email_hash, password_hash)
               VALUES (:pid, :enc, :h, :pw)""",
            {"pid": str(ULID()), "enc": crypto.encrypt(email, "users.email"), "h": email_hash(email),
             "pw": hash_password(data.password)}, conn=conn)
        db.execute("INSERT INTO user_roles (user_id, role) VALUES (:u, 'guest')", {"u": uid}, conn=conn)
        db.execute("INSERT INTO user_profiles (user_id, display_name) VALUES (:u, :n)",
                   {"u": uid, "n": data.display_name}, conn=conn)
    _send_verification(uid, email)
    return _start_session(uid, status=201)


@bp.post("/login")
@limiter.limit("10 per minute")
def login():
    data = body(LoginIn)
    h = email_hash(data.email)
    failures = db.scalar(
        """SELECT COUNT(*) FROM login_attempts
           WHERE email_hash = :h AND success = FALSE AND created_at > NOW() - INTERVAL :m MINUTE""",
        {"h": h, "m": LOCKOUT_WINDOW_MIN})
    if failures >= LOCKOUT_FAILURES:
        raise ApiError(429, "locked_out",
                       f"Too many failed attempts. Try again in {LOCKOUT_WINDOW_MIN} minutes or reset your password.")

    user = db.one("SELECT id, password_hash, status FROM users WHERE email_hash = :h", {"h": h})
    ok = verify_password(user["password_hash"] if user else None, data.password)
    ok = ok and user["status"] == "active"
    db.execute("INSERT INTO login_attempts (email_hash, ip, success) VALUES (:h, :ip, :s)",
               {"h": h, "ip": _client_ip(), "s": ok})
    if not ok:
        raise ApiError(401, "invalid_credentials", "Incorrect email or password.")

    if needs_rehash(user["password_hash"]):
        db.execute("UPDATE users SET password_hash = :p WHERE id = :id",
                   {"p": hash_password(data.password), "id": user["id"]})
    return _start_session(user["id"])


@bp.post("/refresh")
@limiter.limit("30 per minute")
def refresh():
    token = request.cookies.get(tokens.REFRESH_COOKIE)
    rotated = tokens.rotate_refresh_token(token, request.headers.get("User-Agent"), _client_ip()) if token else None
    if not rotated:
        raise ApiError(401, "unauthenticated", "Session expired. Please sign in again.")
    user_id, new_refresh = rotated
    user = load_user(user_id)
    if not user or user["status"] != "active":
        raise ApiError(401, "unauthenticated", "Session expired. Please sign in again.")
    resp = make_response(jsonify(me_payload(user)))
    return tokens.set_auth_cookies(resp, tokens.issue_access_token(user), new_refresh)


@bp.post("/logout")
def logout():
    token = request.cookies.get(tokens.REFRESH_COOKIE)
    if token:
        tokens.revoke_refresh_token(token)
    return tokens.clear_auth_cookies(make_response("", 204))


@bp.get("/me")
@login_required
def me():
    return jsonify(me_payload(g.user))


@bp.post("/verify-email")
@limiter.limit("10 per minute")
def verify_email():
    data = body(TokenIn)
    with db.transaction() as conn:
        uid = _consume_one_time_token(data.token, "verify_email", conn)
        db.execute("UPDATE users SET email_verified_at = COALESCE(email_verified_at, NOW()) WHERE id = :id",
                   {"id": uid}, conn=conn)
    return jsonify(verified=True)


@bp.post("/resend-verification")
@login_required
@limiter.limit("3 per hour")
def resend_verification():
    if g.user["email_verified_at"]:
        return jsonify(verified=True)
    _send_verification(g.user["id"], get_email(g.user["id"]))
    return jsonify(sent=True)


@bp.post("/forgot-password")
@limiter.limit("5 per hour")
def forgot_password():
    data = body(ForgotIn)
    user = db.one("SELECT id, status FROM users WHERE email_hash = :h", {"h": email_hash(data.email)})
    if user and user["status"] == "active":
        token = _issue_one_time_token(user["id"], "reset_password", RESET_TTL)
        link = f"{current_app.config['FRONTEND_URL']}/reset-password?token={token}"
        enqueue(send_email_job, data.email, "Reset your HomeNest password",
                f"Someone asked to reset your password.\n\nReset it here (valid 30 minutes):\n{link}\n\n"
                "If this wasn't you, ignore this email: your password is unchanged.")
    # Same response whether or not the account exists: no user enumeration.
    return jsonify(message="If that email has an account, a reset link is on its way."), 202


@bp.post("/reset-password")
@limiter.limit("10 per hour")
def reset_password():
    data = body(ResetIn)
    if problem := validate_strength(data.password):
        raise ApiError(422, "weak_password", problem)
    with db.transaction() as conn:
        uid = _consume_one_time_token(data.token, "reset_password", conn)
        db.execute("""UPDATE users SET password_hash = :p, email_verified_at = COALESCE(email_verified_at, NOW())
                      WHERE id = :id""", {"p": hash_password(data.password), "id": uid}, conn=conn)
        tokens.revoke_all_for_user(uid, conn=conn)  # sign out every device
    return jsonify(reset=True)


@bp.post("/change-password")
@login_required
@limiter.limit("5 per hour")
def change_password():
    data = body(ChangePasswordIn)
    row = db.one("SELECT password_hash FROM users WHERE id = :id", {"id": g.user["id"]})
    if not verify_password(row["password_hash"], data.current_password):
        raise ApiError(400, "invalid_password", "Your current password is incorrect.")
    if problem := validate_strength(data.new_password):
        raise ApiError(422, "weak_password", problem)
    with db.transaction() as conn:
        db.execute("UPDATE users SET password_hash = :p WHERE id = :id",
                   {"p": hash_password(data.new_password), "id": g.user["id"]}, conn=conn)
        tokens.revoke_all_for_user(g.user["id"], conn=conn)
    return _start_session(g.user["id"])


@bp.get("/sessions")
@login_required
def sessions():
    current = request.cookies.get(tokens.REFRESH_COOKIE)
    current_hash = crypto.sha256(current) if current else None
    rows = db.query(
        """SELECT family_id, user_agent, ip, MIN(created_at) AS signed_in_at, MAX(created_at) AS last_active_at,
                  MAX(token_hash = :cur AND revoked_at IS NULL) AS current
           FROM refresh_tokens
           WHERE user_id = :u AND expires_at > NOW()
           GROUP BY family_id, user_agent, ip
           HAVING SUM(revoked_at IS NULL) > 0
           ORDER BY last_active_at DESC""", {"u": g.user["id"], "cur": current_hash})
    for r in rows:
        r["current"] = bool(r["current"])
    return jsonify(rows)


@bp.delete("/sessions/<family_id>")
@login_required
def revoke_session(family_id):
    db.execute("UPDATE refresh_tokens SET revoked_at = NOW() WHERE user_id = :u AND family_id = :f",
               {"u": g.user["id"], "f": family_id})
    return "", 204
