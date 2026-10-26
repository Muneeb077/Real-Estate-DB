"""
Guest <-> host interactions: conversations (encrypted messages), viewing
requests, offers / rental applications, and reports.
"""
from datetime import date, datetime, timedelta
from typing import Literal, Optional

from flask import Blueprint, g, jsonify
from pydantic import Field
from ulid import ULID

from .. import db
from ..errors import ApiError
from ..extensions import limiter
from ..notify import notify
from ..security import crypto
from ..security.rbac import login_required, verified_required
from .common import Strict, body

bp = Blueprint("interactions", __name__, url_prefix="/api/v1")

MSG_CONTEXT = "messages.body"


class MessageIn(Strict):
    message: str = Field(min_length=1, max_length=4000)


class ViewingIn(Strict):
    scheduled_at: datetime
    note: Optional[str] = Field(None, max_length=500)


class ViewingUpdate(Strict):
    status: Literal["confirmed", "declined", "cancelled"]


class OfferIn(Strict):
    amount: float = Field(gt=0, le=1_000_000_000)
    move_in_date: Optional[date] = None
    message: Optional[str] = Field(None, max_length=1000)


class ReportIn(Strict):
    entity: Literal["listing", "user"]
    public_id: str = Field(max_length=26)
    reason: Literal["spam", "scam", "inaccurate", "offensive", "other"]
    details: Optional[str] = Field(None, max_length=1000)


def _published_listing(public_id, conn=None):
    row = db.one("""SELECT id, host_id, title, listing_mode, price, public_id FROM listings
                    WHERE public_id = :p AND status = 'published' AND deleted_at IS NULL""",
                 {"p": public_id}, conn=conn)
    if not row:
        raise ApiError(404, "not_found", "Listing not found or no longer available.")
    if row["host_id"] == g.user["id"]:
        raise ApiError(400, "own_listing", "You can't do that on your own listing.")
    return row


# ---------------------------------------------------------------- messaging

@bp.post("/listings/<public_id>/conversations")
@verified_required
@limiter.limit("20 per hour")
def start_conversation(public_id):
    data = body(MessageIn)
    with db.transaction() as conn:
        listing = _published_listing(public_id, conn)
        conv = db.one("SELECT id, public_id FROM conversations WHERE listing_id = :l AND guest_id = :g FOR UPDATE",
                      {"l": listing["id"], "g": g.user["id"]}, conn=conn)
        if not conv:
            pid = str(ULID())
            _, cid = db.execute(
                "INSERT INTO conversations (public_id, listing_id, guest_id, host_id) VALUES (:p, :l, :g, :h)",
                {"p": pid, "l": listing["id"], "g": g.user["id"], "h": listing["host_id"]}, conn=conn)
            conv = {"id": cid, "public_id": pid}
        _insert_message(conv["id"], data.message, conn)
        notify(listing["host_id"], "message", f"New message about \"{listing['title']}\"",
               f"/inbox/{conv['public_id']}", conn=conn)
    return jsonify(conversation=conv["public_id"]), 201


def _insert_message(conversation_id, text, conn):
    db.execute("INSERT INTO messages (conversation_id, sender_id, body_enc) VALUES (:c, :s, :b)",
               {"c": conversation_id, "s": g.user["id"], "b": crypto.encrypt(text, MSG_CONTEXT)}, conn=conn)
    db.execute("""UPDATE conversations SET last_message_at = NOW(),
                  guest_read_at = IF(guest_id = :u, NOW(), guest_read_at),
                  host_read_at = IF(host_id = :u, NOW(), host_read_at) WHERE id = :c""",
               {"c": conversation_id, "u": g.user["id"]}, conn=conn)


def _my_conversation(public_id, conn=None):
    conv = db.one("""SELECT id, public_id, guest_id, host_id, listing_id FROM conversations
                     WHERE public_id = :p AND (guest_id = :u OR host_id = :u)""",
                  {"p": public_id, "u": g.user["id"]}, conn=conn)
    if not conv:
        raise ApiError(404, "not_found", "Conversation not found.")
    return conv


@bp.get("/conversations")
@login_required
def conversations():
    rows = db.query(
        """SELECT c.public_id, c.last_message_at, l.public_id AS listing_id, l.title AS listing_title,
                  (SELECT p.thumb_url FROM listing_photos p WHERE p.listing_id = l.id ORDER BY p.sort_order LIMIT 1) AS listing_thumb,
                  IF(c.guest_id = :u, 'guest', 'host') AS my_role,
                  op.display_name AS other_name, op.avatar_url AS other_avatar,
                  (c.last_message_at > COALESCE(IF(c.guest_id = :u, c.guest_read_at, c.host_read_at), '1970-01-01')) AS unread,
                  (SELECT m.body_enc FROM messages m WHERE m.conversation_id = c.id ORDER BY m.id DESC LIMIT 1) AS last_enc
           FROM conversations c
           JOIN listings l ON l.id = c.listing_id
           JOIN user_profiles op ON op.user_id = IF(c.guest_id = :u, c.host_id, c.guest_id)
           WHERE c.guest_id = :u OR c.host_id = :u
           ORDER BY c.last_message_at DESC LIMIT 100""", {"u": g.user["id"]})
    for r in rows:
        enc = r.pop("last_enc")
        r["last_message"] = crypto.decrypt(enc, MSG_CONTEXT)[:140] if enc else ""
        r["unread"] = bool(r["unread"])
    return jsonify(rows)


@bp.get("/conversations/<public_id>")
@login_required
def conversation(public_id):
    conv = _my_conversation(public_id)
    msgs = db.query(
        """SELECT m.id, m.body_enc, m.created_at, (m.sender_id = :u) AS mine, p.display_name AS sender_name
           FROM messages m JOIN user_profiles p ON p.user_id = m.sender_id
           WHERE m.conversation_id = :c ORDER BY m.id""", {"c": conv["id"], "u": g.user["id"]})
    for m in msgs:
        m["body"] = crypto.decrypt(m.pop("body_enc"), MSG_CONTEXT)
        m["mine"] = bool(m["mine"])
    col = "guest_read_at" if conv["guest_id"] == g.user["id"] else "host_read_at"
    db.execute(f"UPDATE conversations SET {col} = NOW() WHERE id = :c", {"c": conv["id"]})
    listing = db.one("SELECT public_id, title, listing_mode FROM listings WHERE id = :l", {"l": conv["listing_id"]})
    other = db.one("""SELECT u.public_id, p.display_name AS name, p.avatar_url FROM users u
                      JOIN user_profiles p ON p.user_id = u.id WHERE u.id = :id""",
                   {"id": conv["host_id"] if conv["guest_id"] == g.user["id"] else conv["guest_id"]})
    return jsonify(public_id=conv["public_id"], listing=listing, other=other, messages=msgs)


@bp.post("/conversations/<public_id>/messages")
@login_required
@limiter.limit("60 per hour")
def send_message(public_id):
    data = body(MessageIn)
    with db.transaction() as conn:
        conv = _my_conversation(public_id, conn)
        _insert_message(conv["id"], data.message, conn)
        recipient = conv["host_id"] if conv["guest_id"] == g.user["id"] else conv["guest_id"]
        notify(recipient, "message", f"New message from {g.user['display_name']}", f"/inbox/{public_id}", conn=conn)
    return "", 201


# ---------------------------------------------------------------- viewings

@bp.post("/listings/<public_id>/viewings")
@verified_required
@limiter.limit("10 per hour")
def request_viewing(public_id):
    data = body(ViewingIn)
    when = data.scheduled_at.replace(tzinfo=None, second=0, microsecond=0)
    if when < datetime.now() + timedelta(hours=2) or when > datetime.now() + timedelta(days=90):
        raise ApiError(422, "bad_time", "Pick a time between 2 hours and 90 days from now.")
    with db.transaction() as conn:
        listing = _published_listing(public_id, conn)
        if listing["listing_mode"] == "short_term_stay":
            raise ApiError(400, "wrong_mode", "Stays are booked directly; viewings are for sales and rentals.")
        pid = str(ULID())
        db.execute("""INSERT INTO viewings (public_id, listing_id, guest_id, scheduled_at, note)
                      VALUES (:p, :l, :g, :t, :n)""",
                   {"p": pid, "l": listing["id"], "g": g.user["id"], "t": when, "n": data.note}, conn=conn)
        notify(listing["host_id"], "viewing_requested",
               f"Viewing requested for \"{listing['title']}\" on {when:%b %d at %H:%M}", "/host/requests", conn=conn)
    return jsonify(public_id=pid, status="requested"), 201


VIEWING_COLUMNS = """v.public_id, v.scheduled_at, v.note, v.status, v.created_at,
                     l.public_id AS listing_id, l.title AS listing_title, l.city"""


@bp.get("/me/viewings")
@login_required
def my_viewings():
    return jsonify(db.query(
        f"""SELECT {VIEWING_COLUMNS} FROM viewings v JOIN listings l ON l.id = v.listing_id
            WHERE v.guest_id = :u ORDER BY v.scheduled_at DESC""", {"u": g.user["id"]}))


@bp.get("/host/viewings")
@login_required
def host_viewings():
    return jsonify(db.query(
        f"""SELECT {VIEWING_COLUMNS}, p.display_name AS guest_name
            FROM viewings v JOIN listings l ON l.id = v.listing_id JOIN user_profiles p ON p.user_id = v.guest_id
            WHERE l.host_id = :u ORDER BY (v.status = 'requested') DESC, v.scheduled_at""", {"u": g.user["id"]}))


@bp.patch("/viewings/<public_id>")
@login_required
def update_viewing(public_id):
    data = body(ViewingUpdate)
    with db.transaction() as conn:
        v = db.one("""SELECT v.id, v.guest_id, v.status, v.scheduled_at, l.host_id, l.title FROM viewings v
                      JOIN listings l ON l.id = v.listing_id WHERE v.public_id = :p FOR UPDATE""",
                   {"p": public_id}, conn=conn)
        if not v or g.user["id"] not in (v["guest_id"], v["host_id"]):
            raise ApiError(404, "not_found", "Viewing not found.")
        is_host = g.user["id"] == v["host_id"]
        allowed = {"confirmed", "declined"} if is_host else {"cancelled"}
        if data.status not in allowed or v["status"] not in ("requested", "confirmed"):
            raise ApiError(409, "bad_transition", "That change isn't possible for this viewing.")
        db.execute("UPDATE viewings SET status = :s WHERE id = :id", {"s": data.status, "id": v["id"]}, conn=conn)
        notify(v["guest_id"] if is_host else v["host_id"], f"viewing_{data.status}",
               f"Viewing for \"{v['title']}\" was {data.status}", "/trips" if is_host else "/host/requests", conn=conn)
    return jsonify(status=data.status)


# ---------------------------------------------------------------- offers

OFFER_COLUMNS = """o.public_id, o.amount, o.move_in_date, o.message, o.status, o.created_at, o.decided_at,
                   l.public_id AS listing_id, l.title AS listing_title, l.listing_mode, l.price AS asking_price,
                   l.currency, l.city"""


@bp.post("/listings/<public_id>/offers")
@verified_required
@limiter.limit("10 per hour")
def make_offer(public_id):
    data = body(OfferIn)
    with db.transaction() as conn:
        listing = _published_listing(public_id, conn)
        if listing["listing_mode"] == "short_term_stay":
            raise ApiError(400, "wrong_mode", "Stays are booked directly.")
        if listing["listing_mode"] == "long_term_rent" and not data.move_in_date:
            raise ApiError(422, "move_in_required", "Tell the host when you'd like to move in.")
        if db.scalar("""SELECT COUNT(*) FROM offers WHERE listing_id = :l AND guest_id = :g AND status = 'pending'""",
                     {"l": listing["id"], "g": g.user["id"]}, conn=conn):
            raise ApiError(409, "pending_offer", "You already have a pending offer on this listing.")
        pid = str(ULID())
        db.execute("""INSERT INTO offers (public_id, listing_id, guest_id, amount, move_in_date, message)
                      VALUES (:p, :l, :g, :a, :m, :msg)""",
                   {"p": pid, "l": listing["id"], "g": g.user["id"], "a": data.amount, "m": data.move_in_date,
                    "msg": data.message}, conn=conn)
        kind = "offer" if listing["listing_mode"] == "sale" else "rental application"
        notify(listing["host_id"], "offer_received", f"New {kind} on \"{listing['title']}\"", "/host/requests",
               conn=conn)
    return jsonify(public_id=pid, status="pending"), 201


@bp.get("/me/offers")
@login_required
def my_offers():
    return jsonify(db.query(
        f"""SELECT {OFFER_COLUMNS} FROM offers o JOIN listings l ON l.id = o.listing_id
            WHERE o.guest_id = :u ORDER BY o.created_at DESC""", {"u": g.user["id"]}))


@bp.get("/host/offers")
@login_required
def host_offers():
    return jsonify(db.query(
        f"""SELECT {OFFER_COLUMNS}, p.display_name AS guest_name
            FROM offers o JOIN listings l ON l.id = o.listing_id JOIN user_profiles p ON p.user_id = o.guest_id
            WHERE l.host_id = :u ORDER BY (o.status = 'pending') DESC, o.created_at DESC""", {"u": g.user["id"]}))


def _offer_for(public_id, conn):
    o = db.one("""SELECT o.id, o.guest_id, o.status, l.host_id, l.title FROM offers o
                  JOIN listings l ON l.id = o.listing_id WHERE o.public_id = :p FOR UPDATE""",
               {"p": public_id}, conn=conn)
    if not o or g.user["id"] not in (o["guest_id"], o["host_id"]):
        raise ApiError(404, "not_found", "Offer not found.")
    return o


@bp.post("/offers/<public_id>/accept")
@login_required
def accept_offer(public_id):
    o = db.one("SELECT o.id FROM offers o JOIN listings l ON l.id = o.listing_id WHERE o.public_id = :p AND l.host_id = :u",
               {"p": public_id, "u": g.user["id"]})
    if not o:
        raise ApiError(404, "not_found", "Offer not found.")
    # The procedure manages its own transaction and locks (see db/procedures/accept_offer.sql).
    result = db.call("AcceptOffer", [o["id"], g.user["id"]])
    return jsonify(status="accepted", transaction=result[0] if result else None)


@bp.post("/offers/<public_id>/decline")
@login_required
def decline_offer(public_id):
    with db.transaction() as conn:
        o = _offer_for(public_id, conn)
        if o["host_id"] != g.user["id"] or o["status"] != "pending":
            raise ApiError(409, "bad_transition", "Only pending offers can be declined by the host.")
        db.execute("UPDATE offers SET status = 'declined', decided_at = NOW() WHERE id = :id", {"id": o["id"]}, conn=conn)
        notify(o["guest_id"], "offer_declined", f"Your offer on \"{o['title']}\" was declined", "/trips", conn=conn)
    return jsonify(status="declined")


@bp.post("/offers/<public_id>/withdraw")
@login_required
def withdraw_offer(public_id):
    with db.transaction() as conn:
        o = _offer_for(public_id, conn)
        if o["guest_id"] != g.user["id"] or o["status"] != "pending":
            raise ApiError(409, "bad_transition", "Only your pending offers can be withdrawn.")
        db.execute("UPDATE offers SET status = 'withdrawn', decided_at = NOW() WHERE id = :id", {"id": o["id"]}, conn=conn)
    return jsonify(status="withdrawn")


# ---------------------------------------------------------------- reports

@bp.post("/reports")
@login_required
@limiter.limit("10 per hour")
def report():
    data = body(ReportIn)
    table = "listings" if data.entity == "listing" else "users"
    row = db.one(f"SELECT id FROM {table} WHERE public_id = :p", {"p": data.public_id})
    if not row:
        raise ApiError(404, "not_found", "Nothing to report.")
    db.execute("""INSERT IGNORE INTO reports (reporter_id, entity, entity_id, reason, details)
                  VALUES (:r, :e, :i, :reason, :d)""",
               {"r": g.user["id"], "e": data.entity, "i": row["id"], "reason": data.reason, "d": data.details})
    return jsonify(received=True), 201
