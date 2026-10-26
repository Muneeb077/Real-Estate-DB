"""
User helpers shared by the auth, profile and admin endpoints.
"""
from . import db
from .security import crypto


def email_hash(email):
    return crypto.blind_index(email.strip().lower(), "users.email")


def get_email(user_id):
    row = db.one("SELECT email_enc FROM users WHERE id = :id", {"id": user_id})
    return crypto.decrypt(row["email_enc"], "users.email") if row else None


def me_payload(user):
    return {
        "public_id": user["public_id"],
        "email": get_email(user["id"]),
        "display_name": user["display_name"],
        "avatar_url": user["avatar_url"],
        "roles": sorted(user["roles"]),
        "email_verified": bool(user["email_verified_at"]),
    }


def user_id_by_public(public_id):
    row = db.one("SELECT id FROM users WHERE public_id = :p", {"p": public_id})
    return row["id"] if row else None
