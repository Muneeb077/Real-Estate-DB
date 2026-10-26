"""
Request authentication and role-based access control.
"""
import hmac
from functools import wraps

from flask import current_app, g, request

from .. import db
from ..errors import ApiError
from . import tokens

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_EXEMPT_PATHS = {"/api/v1/payments/stripe/webhook"}


def load_user(user_id):
    row = db.one(
        """SELECT u.id, u.public_id, u.status, u.email_verified_at, u.mfa_enabled_at,
                  p.display_name, p.avatar_url,
                  (SELECT GROUP_CONCAT(role) FROM user_roles r WHERE r.user_id = u.id) AS roles
           FROM users u LEFT JOIN user_profiles p ON p.user_id = u.id
           WHERE u.id = :id AND u.deleted_at IS NULL""",
        {"id": user_id},
    )
    if not row:
        return None
    row["roles"] = set((row["roles"] or "").split(",")) - {""}
    return row


def authenticate_request():
    """
    before_request hook: resolves g.user from the access cookie and enforces CSRF.
    """
    g.user = None
    g.mfa = False
    token = request.cookies.get(tokens.ACCESS_COOKIE)
    if token:
        claims = tokens.decode(token)
        if claims:
            user = load_user(int(claims["sub"]))
            if user and user["status"] == "active":
                g.user = user
                g.mfa = bool(claims.get("mfa"))

    if request.method not in SAFE_METHODS and request.path not in CSRF_EXEMPT_PATHS:
        cookie = request.cookies.get(tokens.CSRF_COOKIE)
        header = request.headers.get("X-CSRF-Token")
        # Unauthenticated POSTs (login/signup) still need a token: GET /auth/csrf issues one.
        if not cookie or not header or not hmac.compare_digest(cookie, header):
            raise ApiError(403, "csrf_failed", "Missing or invalid CSRF token.")


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.get("user") is None:
            raise ApiError(401, "unauthenticated", "Please sign in.")
        return view(*args, **kwargs)
    return wrapper


def verified_required(view):
    @login_required
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_app.config["REQUIRE_VERIFIED_EMAIL"] and not g.user["email_verified_at"]:
            raise ApiError(403, "email_unverified", "Please verify your email address first.")
        return view(*args, **kwargs)
    return wrapper


def roles_required(*roles):
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not g.user["roles"] & set(roles):
                raise ApiError(403, "forbidden", "You do not have access to this resource.")
            if "admin" in roles and roles == ("admin",) and current_app.config["ADMIN_REQUIRE_MFA"]:
                if not g.user["mfa_enabled_at"]:
                    raise ApiError(403, "mfa_setup_required", "Admins must enable two-factor authentication.")
                if not g.mfa:
                    raise ApiError(403, "mfa_required", "Sign in again with your authenticator code.")
            return view(*args, **kwargs)
        return wrapper
    return decorator


admin_required = roles_required("admin")
host_required = roles_required("host", "admin")
