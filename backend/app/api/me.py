"""
The signed-in user's own data: profile (encrypted phone), wishlist, saved searches,
notifications, data export and account deletion.
"""
import json
import secrets
from typing import Optional

from flask import Blueprint, g, jsonify, make_response
from pydantic import Field, HttpUrl

from .. import db
from ..errors import ApiError
from ..security import crypto, tokens
from ..security.passwords import verify_password
from ..security.rbac import login_required
from ..users import me_payload
from .common import Strict, body
from .listings import card_columns

bp = Blueprint("me", __name__, url_prefix="/api/v1/me")


class ProfileIn(Strict):
    display_name: Optional[str] = Field(None, min_length=2, max_length=120)
    bio: Optional[str] = Field(None, max_length=1000)
    phone: Optional[str] = Field(None, pattern=r"^\+?[0-9 ()-]{7,20}$")
    avatar_url: Optional[HttpUrl] = None


class SavedSearchIn(Strict):
    name: str = Field(min_length=1, max_length=100)
    query: dict
    alerts: bool = True


class DeleteIn(Strict):
    password: str = Field(max_length=200)


def _listing_id(public_id):
    row = db.one("SELECT id FROM v_public_listings WHERE public_id = :p", {"p": public_id})
    if not row:
        raise ApiError(404, "not_found", "Listing not found.")
    return row["id"]


@bp.get("/profile")
@login_required
def get_profile():
    p = db.one("SELECT display_name, bio, avatar_url, phone_enc FROM user_profiles WHERE user_id = :u",
               {"u": g.user["id"]})
    p["phone"] = crypto.decrypt(p.pop("phone_enc"), "user_profiles.phone") if p["phone_enc"] else None
    return jsonify(p)


@bp.patch("/profile")
@login_required
def update_profile():
    data = body(ProfileIn).model_dump(exclude_unset=True)
    sets, params = [], {"u": g.user["id"]}
    for field in ("display_name", "bio"):
        if field in data:
            sets.append(f"{field} = :{field}")
            params[field] = data[field]
    if "avatar_url" in data:
        sets.append("avatar_url = :avatar_url")
        params["avatar_url"] = str(data["avatar_url"]) if data["avatar_url"] else None
    if "phone" in data:
        phone = data["phone"]
        normalised = "".join(c for c in phone if c.isdigit() or c == "+") if phone else None
        sets += ["phone_enc = :pe", "phone_hash = :ph"]
        params["pe"] = crypto.encrypt(normalised, "user_profiles.phone") if normalised else None
        params["ph"] = crypto.blind_index(normalised, "user_profiles.phone") if normalised else None
    if sets:
        db.execute(f"UPDATE user_profiles SET {', '.join(sets)} WHERE user_id = :u", params)
    return get_profile()


@bp.get("/favorites")
@login_required
def favorites():
    rows = db.query(
        f"""SELECT {card_columns()} FROM favorites f JOIN v_public_listings v ON v.id = f.listing_id
            WHERE f.user_id = :u ORDER BY f.created_at DESC""", {"u": g.user["id"]})
    return jsonify(rows)


@bp.get("/favorites/ids")
@login_required
def favorite_ids():
    rows = db.query("""SELECT l.public_id FROM favorites f JOIN listings l ON l.id = f.listing_id
                       WHERE f.user_id = :u""", {"u": g.user["id"]})
    return jsonify([r["public_id"] for r in rows])


@bp.put("/favorites/<public_id>")
@login_required
def add_favorite(public_id):
    db.execute("INSERT IGNORE INTO favorites (user_id, listing_id) VALUES (:u, :l)",
               {"u": g.user["id"], "l": _listing_id(public_id)})
    return "", 204


@bp.delete("/favorites/<public_id>")
@login_required
def remove_favorite(public_id):
    db.execute("""DELETE f FROM favorites f JOIN listings l ON l.id = f.listing_id
                  WHERE f.user_id = :u AND l.public_id = :p""", {"u": g.user["id"], "p": public_id})
    return "", 204


@bp.get("/saved-searches")
@login_required
def saved_searches():
    rows = db.query("SELECT id, name, query, alerts, created_at FROM saved_searches WHERE user_id = :u ORDER BY id DESC",
                    {"u": g.user["id"]})
    for r in rows:
        r["query"] = json.loads(r["query"])
    return jsonify(rows)


@bp.post("/saved-searches")
@login_required
def create_saved_search():
    data = body(SavedSearchIn)
    allowed = {"q", "mode", "type", "city", "min_price", "max_price", "beds", "baths", "guests", "amenities", "sort"}
    query = {k: str(v) for k, v in data.query.items() if k in allowed and v not in (None, "")}
    if db.scalar("SELECT COUNT(*) FROM saved_searches WHERE user_id = :u", {"u": g.user["id"]}) >= 20:
        raise ApiError(409, "limit", "You can keep up to 20 saved searches.")
    _, sid = db.execute(
        """INSERT INTO saved_searches (user_id, name, query, alerts, last_notified_at)
           VALUES (:u, :n, :q, :a, NOW())""",
        {"u": g.user["id"], "n": data.name, "q": json.dumps(query), "a": data.alerts})
    return jsonify(id=sid, name=data.name, query=query, alerts=data.alerts), 201


@bp.delete("/saved-searches/<int:sid>")
@login_required
def delete_saved_search(sid):
    db.execute("DELETE FROM saved_searches WHERE id = :id AND user_id = :u", {"id": sid, "u": g.user["id"]})
    return "", 204


@bp.get("/notifications")
@login_required
def notifications():
    rows = db.query("""SELECT id, kind, title, link, read_at, created_at FROM notifications
                       WHERE user_id = :u ORDER BY id DESC LIMIT 50""", {"u": g.user["id"]})
    unread = db.scalar("SELECT COUNT(*) FROM notifications WHERE user_id = :u AND read_at IS NULL",
                       {"u": g.user["id"]})
    return jsonify(items=rows, unread=unread)


@bp.post("/notifications/read")
@login_required
def mark_read():
    db.execute("UPDATE notifications SET read_at = NOW() WHERE user_id = :u AND read_at IS NULL", {"u": g.user["id"]})
    return "", 204


@bp.get("/export")
@login_required
def export():
    """
    Everything we hold about the user, decrypted, as a downloadable JSON file.
    """
    uid = g.user["id"]
    profile = db.one("SELECT display_name, bio, avatar_url, phone_enc FROM user_profiles WHERE user_id = :u", {"u": uid})
    profile["phone"] = crypto.decrypt(profile.pop("phone_enc"), "user_profiles.phone") if profile["phone_enc"] else None
    data = {
        "account": me_payload(g.user),
        "profile": profile,
        "favorites": [r["public_id"] for r in db.query(
            "SELECT l.public_id FROM favorites f JOIN listings l ON l.id = f.listing_id WHERE f.user_id = :u", {"u": uid})],
        "saved_searches": db.query("SELECT name, query, created_at FROM saved_searches WHERE user_id = :u", {"u": uid}),
        "offers": db.query("""SELECT o.public_id, l.public_id AS listing, o.amount, o.status, o.created_at
                              FROM offers o JOIN listings l ON l.id = o.listing_id WHERE o.guest_id = :u""", {"u": uid}),
        "viewings": db.query("""SELECT v.public_id, l.public_id AS listing, v.scheduled_at, v.status
                                FROM viewings v JOIN listings l ON l.id = v.listing_id WHERE v.guest_id = :u""",
                             {"u": uid}),
        "messages_sent": [
            {"conversation": m["conversation"], "sent_at": m["created_at"],
             "body": crypto.decrypt(m["body_enc"], "messages.body")}
            for m in db.query("""SELECT c.public_id AS conversation, m.body_enc, m.created_at FROM messages m
                                 JOIN conversations c ON c.id = m.conversation_id WHERE m.sender_id = :u""", {"u": uid})
        ],
        "sessions": db.query("""SELECT user_agent, ip, created_at, revoked_at FROM refresh_tokens
                                WHERE user_id = :u ORDER BY id DESC LIMIT 100""", {"u": uid}),
    }
    resp = make_response(json.dumps(data, indent=2, default=str))
    resp.headers["Content-Type"] = "application/json"
    resp.headers["Content-Disposition"] = "attachment; filename=homenest-export.json"
    return resp


@bp.delete("")
@login_required
def delete_account():
    """
    Soft delete: personal data is scrubbed, rows that other people depend on
    (messages, transactions, reviews) stay linked to an anonymised account.
    """
    data = body(DeleteIn)
    uid = g.user["id"]
    row = db.one("SELECT password_hash FROM users WHERE id = :id", {"id": uid})
    if not verify_password(row["password_hash"], data.password):
        raise ApiError(400, "invalid_password", "Your password is incorrect.")
    if db.scalar("SELECT COUNT(*) FROM listings WHERE host_id = :u AND status = 'published'", {"u": uid}):
        raise ApiError(409, "active_listings", "Unpublish your listings before deleting your account.")
    placeholder = f"deleted-{secrets.token_hex(8)}@deleted.invalid"
    with db.transaction() as conn:
        db.execute(
            """UPDATE users SET status = 'deleted', deleted_at = NOW(), email_enc = :e, email_hash = :h,
                      password_hash = '!', mfa_secret_enc = NULL, mfa_enabled_at = NULL, mfa_recovery_hashes = NULL
               WHERE id = :id""",
            {"e": crypto.encrypt(placeholder, "users.email"), "h": crypto.blind_index(placeholder, "users.email"),
             "id": uid}, conn=conn)
        db.execute("""UPDATE user_profiles SET display_name = 'Deleted user', bio = NULL, avatar_url = NULL,
                      phone_enc = NULL, phone_hash = NULL WHERE user_id = :id""", {"id": uid}, conn=conn)
        db.execute("DELETE FROM favorites WHERE user_id = :id", {"id": uid}, conn=conn)
        db.execute("DELETE FROM saved_searches WHERE user_id = :id", {"id": uid}, conn=conn)
        tokens.revoke_all_for_user(uid, conn=conn)
    return tokens.clear_auth_cookies(make_response("", 204))

