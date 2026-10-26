"""
Admin console API. Every route requires the admin role (see rbac.roles_required). Writes are attributed via @actor_id and recorded
by the audit triggers; reading decrypted PII is logged explicitly here.
"""
import json
import os
from typing import Literal, Optional

from flask import Blueprint, current_app, g, jsonify, request, send_file
from pydantic import Field

from .. import db
from ..errors import ApiError
from ..extensions import cache
from ..notify import notify
from ..security import crypto
from ..security.rbac import admin_required
from ..tasks import enqueue
from ..users import email_hash
from .common import Strict, body

bp = Blueprint("admin", __name__, url_prefix="/api/v1/admin")


class UserUpdate(Strict):
    status: Optional[Literal["active", "suspended"]] = None
    roles: Optional[list[Literal["guest", "host", "admin"]]] = None


class ModerateIn(Strict):
    decision: Literal["approve", "reject"]
    note: Optional[str] = Field(None, max_length=500)


class VerifyIn(Strict):
    decision: Literal["verified", "rejected"]


class ReportIn(Strict):
    status: Literal["dismissed", "actioned"]
    hide_listing: bool = False


class ReviewModIn(Strict):
    hidden: bool


class SettingsIn(Strict):
    service_fee_rate: Optional[float] = Field(None, ge=0, le=0.3)
    default_commission_rate: Optional[float] = Field(None, ge=0, le=0.2)
    booking_hold_minutes: Optional[int] = Field(None, ge=5, le=120)
    new_listings_require_review: Optional[bool] = None


def _audit(action, entity, entity_id=None, data=None):
    db.execute("""INSERT INTO audit_log (actor_id, action, entity, entity_id, new_data, ip)
                  VALUES (:a, :ac, :e, :id, :d, :ip)""",
               {"a": g.user["id"], "ac": action, "e": entity, "id": entity_id,
                "d": json.dumps(data) if data else None, "ip": request.remote_addr})


@bp.get("/kpis")
@admin_required
def kpis():
    key = f"admin:kpis:{cache.version('listings')}"
    data = cache.get(key)
    if data is None:
        data = {
            "totals": db.call("AdminKpis", [], read=True)[0],
            "monthly": db.call("AdminMonthlyGmv", [], read=True),
            "top_hosts": db.call("AdminTopHosts", [], read=True),
            "cities": db.call("AdminCityStats", [], read=True),
        }
        cache.set(key, data, ttl=120)
    return jsonify(data)


@bp.get("/users")
@admin_required
def users():
    q = (request.args.get("q") or "").strip()
    role = request.args.get("role")
    status = request.args.get("status")
    where, params = ["u.deleted_at IS NULL"], {}
    if q:
        if "@" in q:
            # exact email lookup through the blind index: the DB never sees the plaintext
            where.append("u.email_hash = :eh")
            params["eh"] = email_hash(q)
        else:
            where.append("p.display_name LIKE :name")
            params["name"] = f"%{q}%"
    if role in ("guest", "host", "admin"):
        where.append("EXISTS (SELECT 1 FROM user_roles r WHERE r.user_id = u.id AND r.role = :role)")
        params["role"] = role
    if status in ("active", "suspended"):
        where.append("u.status = :status")
        params["status"] = status
    rows = db.query(
        f"""SELECT u.id, u.public_id, u.email_enc, u.status, u.email_verified_at IS NOT NULL AS verified,
                   u.created_at, p.display_name, p.avatar_url,
                   (SELECT GROUP_CONCAT(role ORDER BY role) FROM user_roles r WHERE r.user_id = u.id) AS roles,
                   (SELECT MAX(created_at) FROM refresh_tokens t WHERE t.user_id = u.id) AS last_seen
            FROM users u JOIN user_profiles p ON p.user_id = u.id
            WHERE {' AND '.join(where)}
            ORDER BY u.id DESC LIMIT 100""", params)
    for r in rows:
        r["email"] = crypto.decrypt(r.pop("email_enc"), "users.email")
        r["roles"] = (r["roles"] or "").split(",")
        r["verified"] = bool(r["verified"])
        r.pop("id")
    _audit("pii.view", "user", data={"view": "user_list", "count": len(rows), "query": q[:50]})
    return jsonify(rows)


@bp.patch("/users/<public_id>")
@admin_required
def update_user(public_id):
    data = body(UserUpdate)
    target = db.one("SELECT id FROM users WHERE public_id = :p", {"p": public_id})
    if not target:
        raise ApiError(404, "not_found", "User not found.")
    if target["id"] == g.user["id"] and (data.status == "suspended" or (data.roles is not None and "admin" not in data.roles)):
        raise ApiError(409, "self_lockout", "You can't suspend yourself or remove your own admin role.")
    with db.transaction() as conn:
        if data.status:
            db.execute("UPDATE users SET status = :s WHERE id = :id", {"s": data.status, "id": target["id"]}, conn=conn)
            if data.status == "suspended":
                db.execute("UPDATE refresh_tokens SET revoked_at = NOW() WHERE user_id = :id AND revoked_at IS NULL",
                           {"id": target["id"]}, conn=conn)
        if data.roles is not None:
            current = {r["role"] for r in db.query("SELECT role FROM user_roles WHERE user_id = :id",
                                                   {"id": target["id"]}, conn=conn)}
            for r in set(data.roles) - current:
                db.execute("INSERT INTO user_roles (user_id, role) VALUES (:u, :r)", {"u": target["id"], "r": r}, conn=conn)
            for r in current - set(data.roles):
                db.execute("DELETE FROM user_roles WHERE user_id = :u AND role = :r", {"u": target["id"], "r": r}, conn=conn)
    return jsonify(updated=True)


@bp.get("/listings")
@admin_required
def moderation_queue():
    status = request.args.get("status", "pending_review")
    if status not in ("pending_review", "published", "rejected", "paused"):
        raise ApiError(422, "bad_status", "Unknown status filter.")
    return jsonify(db.query(
        """SELECT l.public_id, l.title, l.description, l.listing_mode, l.property_type, l.price, l.price_unit,
                  l.currency, l.city, l.status, l.moderation_note, l.updated_at, p.display_name AS host_name,
                  h.verification_status AS host_verification,
                  (SELECT COUNT(*) FROM listing_photos ph WHERE ph.listing_id = l.id) AS photos,
                  (SELECT ph.thumb_url FROM listing_photos ph WHERE ph.listing_id = l.id ORDER BY ph.sort_order LIMIT 1) AS thumb
           FROM listings l JOIN user_profiles p ON p.user_id = l.host_id
           LEFT JOIN host_profiles h ON h.user_id = l.host_id
           WHERE l.status = :s AND l.deleted_at IS NULL
           ORDER BY l.updated_at LIMIT 100""", {"s": status}))


@bp.post("/listings/<public_id>/moderate")
@admin_required
def moderate(public_id):
    data = body(ModerateIn)
    if data.decision == "reject" and not data.note:
        raise ApiError(422, "note_required", "Tell the host why the listing was rejected.")
    listing = db.one("SELECT id, host_id, title, status FROM listings WHERE public_id = :p", {"p": public_id})
    if not listing or listing["status"] != "pending_review":
        raise ApiError(409, "not_pending", "This listing isn't waiting for review.")
    new = "published" if data.decision == "approve" else "rejected"
    with db.transaction() as conn:
        db.execute("UPDATE listings SET status = :s, moderation_note = :n WHERE id = :id",
                   {"s": new, "n": data.note, "id": listing["id"]}, conn=conn)
        notify(listing["host_id"], f"listing_{new}",
               f"\"{listing['title']}\" was {'approved and is live' if new == 'published' else 'not approved'}",
               f"/host/listings/{public_id}", conn=conn)
    cache.bump("listings")
    return jsonify(status=new)


@bp.get("/hosts")
@admin_required
def hosts():
    status = request.args.get("verification", "pending")
    rows = db.query(
        """SELECT u.public_id, p.display_name AS name, h.agency_name, h.license_enc, h.verification_status,
                  h.commission_rate, h.created_at,
                  (SELECT COUNT(*) FROM listings l WHERE l.host_id = u.id AND l.status = 'published') AS listings
           FROM host_profiles h JOIN users u ON u.id = h.user_id JOIN user_profiles p ON p.user_id = u.id
           WHERE h.verification_status = :s ORDER BY h.created_at LIMIT 100""", {"s": status})
    for r in rows:
        r["license_number"] = crypto.decrypt(r.pop("license_enc"), "host_profiles.license") if r["license_enc"] else None
    _audit("pii.view", "host", data={"view": "host_verification", "count": len(rows)})
    return jsonify(rows)


@bp.post("/hosts/<public_id>/verify")
@admin_required
def verify_host(public_id):
    data = body(VerifyIn)
    host = db.one("SELECT u.id FROM users u JOIN host_profiles h ON h.user_id = u.id WHERE u.public_id = :p", {"p": public_id})
    if not host:
        raise ApiError(404, "not_found", "Host not found.")
    with db.transaction() as conn:
        db.execute("""UPDATE host_profiles SET verification_status = :s,
                      verified_at = IF(:s = 'verified', NOW(), NULL) WHERE user_id = :id""",
                   {"s": data.decision, "id": host["id"]}, conn=conn)
        notify(host["id"], "host_verification", f"Your host verification was {data.decision}", "/host", conn=conn)
    return jsonify(status=data.decision)


@bp.get("/reports")
@admin_required
def reports():
    status = request.args.get("status", "open")
    return jsonify(db.query(
        """SELECT r.id, r.entity, r.reason, r.details, r.status, r.created_at, rp.display_name AS reporter,
                  CASE r.entity WHEN 'listing' THEN (SELECT l.public_id FROM listings l WHERE l.id = r.entity_id)
                                WHEN 'user' THEN (SELECT u.public_id FROM users u WHERE u.id = r.entity_id) END AS target_public_id,
                  CASE r.entity WHEN 'listing' THEN (SELECT l.title FROM listings l WHERE l.id = r.entity_id)
                                WHEN 'user' THEN (SELECT p.display_name FROM user_profiles p WHERE p.user_id = r.entity_id) END AS target_name,
                  COUNT(*) OVER (PARTITION BY r.entity, r.entity_id) AS reports_on_target
           FROM reports r JOIN user_profiles rp ON rp.user_id = r.reporter_id
           WHERE r.status = :s ORDER BY reports_on_target DESC, r.created_at LIMIT 100""", {"s": status}))


@bp.post("/reports/<int:report_id>")
@admin_required
def resolve_report(report_id):
    data = body(ReportIn)
    report = db.one("SELECT entity, entity_id FROM reports WHERE id = :id AND status = 'open'", {"id": report_id})
    if not report:
        raise ApiError(404, "not_found", "Open report not found.")
    with db.transaction() as conn:
        db.execute("""UPDATE reports SET status = :s, resolved_by = :u, resolved_at = NOW()
                      WHERE entity = :e AND entity_id = :id AND status = 'open'""",
                   {"s": data.status, "u": g.user["id"], "e": report["entity"], "id": report["entity_id"]}, conn=conn)
        if data.hide_listing and report["entity"] == "listing":
            db.execute("UPDATE listings SET status = 'paused', moderation_note = 'Paused after a report review' "
                       "WHERE id = :id AND status = 'published'", {"id": report["entity_id"]}, conn=conn)
    cache.bump("listings")
    return jsonify(status=data.status)


@bp.get("/reviews")
@admin_required
def recent_reviews():
    return jsonify(db.query(
        """SELECT r.id, r.rating, r.comment, r.hidden_at IS NOT NULL AS hidden, r.created_at, l.public_id AS listing_id,
                  l.title AS listing_title, p.display_name AS author
           FROM reviews r JOIN listings l ON l.id = r.listing_id JOIN user_profiles p ON p.user_id = r.author_id
           ORDER BY (r.rating <= 2) DESC, r.id DESC LIMIT 50"""))


@bp.patch("/reviews/<int:review_id>")
@admin_required
def moderate_review(review_id):
    data = body(ReviewModIn)
    db.execute("UPDATE reviews SET hidden_at = IF(:h, NOW(), NULL) WHERE id = :id", {"h": data.hidden, "id": review_id})
    cache.bump("listings")
    return jsonify(hidden=data.hidden)


@bp.get("/audit")
@admin_required
def audit():
    before = request.args.get("before", type=int)
    entity = request.args.get("entity")
    where, params = ["1 = 1"], {}
    if before:
        where.append("a.id < :before")
        params["before"] = before
    if entity:
        where.append("a.entity = :entity")
        params["entity"] = entity
    rows = db.query(
        f"""SELECT a.id, a.action, a.entity, a.entity_id, a.old_data, a.new_data, a.ip, a.created_at,
                   p.display_name AS actor
            FROM audit_log a LEFT JOIN user_profiles p ON p.user_id = a.actor_id
            WHERE {' AND '.join(where)} ORDER BY a.id DESC LIMIT 50""", params)
    for r in rows:
        for k in ("old_data", "new_data"):
            r[k] = json.loads(r[k]) if r[k] else None
    return jsonify(items=rows, next_before=rows[-1]["id"] if len(rows) == 50 else None)


@bp.get("/settings")
@admin_required
def get_settings():
    return jsonify({r["k"]: json.loads(r["v"]) for r in db.query("SELECT k, v FROM settings")})


@bp.patch("/settings")
@admin_required
def update_settings():
    data = body(SettingsIn).model_dump(exclude_none=True)
    with db.transaction() as conn:
        for k, v in data.items():
            db.execute("UPDATE settings SET v = :v, updated_by = :u WHERE k = :k",
                       {"v": json.dumps(v), "u": g.user["id"], "k": k}, conn=conn)
    return get_settings()


@bp.get("/backups")
@admin_required
def backups():
    return jsonify(db.query("""SELECT b.id, b.file_name, b.size_bytes, b.sha256, b.kek_id, b.status, b.error,
                                      b.created_at, b.finished_at, p.display_name AS created_by
                               FROM backups b LEFT JOIN user_profiles p ON p.user_id = b.created_by
                               ORDER BY b.id DESC LIMIT 30"""))


@bp.post("/backups")
@admin_required
def start_backup():
    from ..backups import run_backup_job
    if not current_app.config.get("BACKUP_DATABASE_URL"):
        raise ApiError(503, "backups_not_configured", "Set BACKUP_DATABASE_URL to enable backups.")
    if db.scalar("SELECT COUNT(*) FROM backups WHERE status = 'running' AND created_at > NOW() - INTERVAL 1 HOUR"):
        raise ApiError(409, "backup_running", "A backup is already running.")
    _, bid = db.execute("INSERT INTO backups (created_by) VALUES (:u)", {"u": g.user["id"]})
    enqueue(run_backup_job, bid)
    return jsonify(id=bid, status="running"), 202


@bp.get("/backups/<int:backup_id>/download")
@admin_required
def download_backup(backup_id):
    """
    Streams the ENCRYPTED file. It can only be restored with the KEK
    (scripts/decrypt_backup.py), so a leaked download is useless on its own.
    """
    b = db.one("SELECT file_name FROM backups WHERE id = :id AND status = 'succeeded'", {"id": backup_id})
    if not b:
        raise ApiError(404, "not_found", "Backup not found.")
    path = os.path.join(current_app.config["BACKUP_DIR"], b["file_name"])
    if not os.path.isfile(path):
        raise ApiError(410, "gone", "The backup file is no longer on this server.")
    _audit("backup.download", "backup", backup_id)
    return send_file(path, as_attachment=True, download_name=b["file_name"], mimetype="application/octet-stream")
