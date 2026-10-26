"""
Short-term stays: availability, quotes, bookings, payments, cancellations, reviews.
The booking rules live in stored procedures (db/procedures/stays.sql); this module
validates input, maps users to ids and talks to the payment provider.
"""
import secrets
from datetime import date

from flask import Blueprint, current_app, g, jsonify, request
from pydantic import Field, model_validator
from ulid import ULID

from .. import db
from ..errors import ApiError
from ..extensions import cache, limiter
from ..security import crypto
from ..security.rbac import login_required, verified_required
from .common import Strict, args, body

bp = Blueprint("stays", __name__, url_prefix="/api/v1")


class StayDates(Strict):
    check_in: date
    check_out: date
    guests: int = Field(1, ge=1, le=50)

    @model_validator(mode="after")
    def order(self):
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")
        return self


class ReviewIn(Strict):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=10, max_length=2000)


class ReplyIn(Strict):
    reply: str = Field(min_length=2, max_length=2000)


def _stay_listing(public_id):
    row = db.one("""SELECT id, host_id, max_guests, price, currency FROM listings
                    WHERE public_id = :p AND listing_mode = 'short_term_stay' AND status = 'published'""",
                 {"p": public_id})
    if not row:
        raise ApiError(404, "not_found", "Stay not found.")
    return row


@bp.get("/listings/<public_id>/availability")
def availability(public_id):
    """
    Unavailable nights for the next 12 months (dates only: who booked is never exposed).
    """
    listing = _stay_listing(public_id)
    rows = db.query(
        """WITH RECURSIVE days (d) AS (
               SELECT CURDATE() UNION ALL SELECT d + INTERVAL 1 DAY FROM days WHERE d < CURDATE() + INTERVAL 365 DAY
           )
           SELECT d FROM days
           WHERE EXISTS (SELECT 1 FROM bookings b WHERE b.listing_id = :l
                           AND (b.status = 'confirmed' OR (b.status = 'pending' AND b.hold_expires_at > NOW()))
                           AND d >= b.check_in AND d < b.check_out)
              OR EXISTS (SELECT 1 FROM blocked_dates bd WHERE bd.listing_id = :l AND bd.day = d)""",
        {"l": listing["id"]})
    return jsonify(unavailable=[r["d"] for r in rows])


@bp.get("/listings/<public_id>/quote")
@limiter.limit("60 per minute")
def quote(public_id):
    p = args(StayDates)
    listing = _stay_listing(public_id)
    q = db.call("QuoteStay", [listing["id"], p.check_in, p.check_out, p.guests], read=True)[0]
    q["available"] = bool(q["available"])
    q["currency"] = listing["currency"]
    return jsonify(q)


@bp.post("/listings/<public_id>/bookings")
@verified_required
@limiter.limit("20 per hour")
def create_booking(public_id):
    data = body(StayDates)
    key = request.headers.get("Idempotency-Key") or secrets.token_hex(16)
    if len(key) > 64:
        raise ApiError(400, "bad_idempotency_key", "Idempotency-Key must be at most 64 characters.")
    listing = _stay_listing(public_id)
    # CreateBooking runs its own transaction with a listing row lock.
    row = db.call("CreateBooking", [listing["id"], g.user["id"], data.check_in, data.check_out, data.guests,
                                    str(ULID()), key])[0]
    return jsonify(row), 201


def _booking(public_id, conn=None):
    b = db.one(
        """SELECT b.*, l.public_id AS listing_public_id, l.title AS listing_title, l.address_id,
                  (SELECT p.thumb_url FROM listing_photos p WHERE p.listing_id = l.id ORDER BY p.sort_order LIMIT 1) AS listing_thumb
           FROM bookings b JOIN listings l ON l.id = b.listing_id WHERE b.public_id = :p""",
        {"p": public_id}, conn=conn)
    if not b or g.user["id"] not in (b["guest_id"], b["host_id"]):
        raise ApiError(404, "not_found", "Booking not found.")
    return b


BOOKING_FIELDS = ("public_id", "check_in", "check_out", "nights", "guests", "subtotal", "service_fee", "total_price",
                  "currency", "status", "hold_expires_at", "cancelled_by", "refund_amount", "created_at",
                  "listing_public_id", "listing_title", "listing_thumb")


@bp.get("/bookings/<public_id>")
@login_required
def booking_detail(public_id):
    b = _booking(public_id)
    out = {k: b[k] for k in BOOKING_FIELDS}
    out["my_role"] = "guest" if b["guest_id"] == g.user["id"] else "host"
    out["review"] = db.one("SELECT rating, comment, host_reply, created_at FROM reviews WHERE booking_id = :b",
                           {"b": b["id"]})
    if b["status"] in ("confirmed", "completed"):
        # The exact address and the other party's phone are decrypted only for
        # the two people on a confirmed booking.
        addr = db.one("SELECT street_enc, city, postal_code, country FROM addresses WHERE id = :a", {"a": b["address_id"]})
        out["address"] = {
            "street": crypto.decrypt(addr["street_enc"], "addresses.street") if addr["street_enc"] else None,
            "city": addr["city"], "postal_code": addr["postal_code"], "country": addr["country"],
        }
        other_id = b["host_id"] if out["my_role"] == "guest" else b["guest_id"]
        other = db.one("SELECT display_name, phone_enc FROM user_profiles WHERE user_id = :u", {"u": other_id})
        out["contact"] = {
            "name": other["display_name"],
            "phone": crypto.decrypt(other["phone_enc"], "user_profiles.phone") if other["phone_enc"] else None,
        }
    return jsonify(out)


@bp.get("/me/bookings")
@login_required
def my_bookings():
    return jsonify(db.query(
        """SELECT b.public_id, b.check_in, b.check_out, b.nights, b.guests, b.total_price, b.currency, b.status,
                  b.hold_expires_at, l.public_id AS listing_public_id, l.title AS listing_title, l.city,
                  (SELECT p.thumb_url FROM listing_photos p WHERE p.listing_id = l.id ORDER BY p.sort_order LIMIT 1) AS listing_thumb,
                  EXISTS (SELECT 1 FROM reviews r WHERE r.booking_id = b.id) AS reviewed
           FROM bookings b JOIN listings l ON l.id = b.listing_id
           WHERE b.guest_id = :u AND b.status <> 'expired'
           ORDER BY b.check_in DESC""", {"u": g.user["id"]}))


@bp.get("/host/bookings")
@login_required
def host_bookings():
    return jsonify(db.query(
        """SELECT b.public_id, b.check_in, b.check_out, b.nights, b.guests, b.total_price, b.currency, b.status,
                  l.public_id AS listing_public_id, l.title AS listing_title, p.display_name AS guest_name
           FROM bookings b JOIN listings l ON l.id = b.listing_id JOIN user_profiles p ON p.user_id = b.guest_id
           WHERE b.host_id = :u AND b.status IN ('confirmed','completed','cancelled')
           ORDER BY b.check_in DESC LIMIT 200""", {"u": g.user["id"]}))


@bp.post("/bookings/<public_id>/pay")
@login_required
@limiter.limit("20 per hour")
def pay(public_id):
    b = _booking(public_id)
    if b["guest_id"] != g.user["id"]:
        raise ApiError(404, "not_found", "Booking not found.")
    if b["status"] != "pending":
        raise ApiError(409, "not_pending", "This booking is not awaiting payment.")

    if current_app.config.get("STRIPE_SECRET_KEY"):
        import stripe
        stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
        front = current_app.config["FRONTEND_URL"]
        session = stripe.checkout.Session.create(
            mode="payment",
            client_reference_id=b["public_id"],
            line_items=[{
                "quantity": 1,
                "price_data": {
                    "currency": b["currency"].lower(),
                    "unit_amount": int(round(float(b["total_price"]) * 100)),
                    "product_data": {"name": f"{b['listing_title']} · {b['nights']} nights"},
                },
            }],
            metadata={"booking": b["public_id"]},
            success_url=f"{front}/trips/{b['public_id']}?paid=1",
            cancel_url=f"{front}/trips/{b['public_id']}",
        )
        return jsonify(checkout_url=session.url)

    # Simulated provider for demos: behaves like an instantly successful card payment.
    db.call("ConfirmBooking", [b["id"], "simulated", f"sim_{secrets.token_hex(12)}"])
    cache.bump("listings")
    return jsonify(status="confirmed")


@bp.post("/payments/stripe/webhook")
def stripe_webhook():
    """
    Stripe calls this after checkout. The signature is verified with the webhook
    secret, so forged requests are rejected (this route is exempt from CSRF).
    """
    secret = current_app.config.get("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise ApiError(404, "not_found", "Not found.")
    import stripe
    try:
        event = stripe.Webhook.construct_event(request.get_data(), request.headers.get("Stripe-Signature", ""), secret)
    except (ValueError, stripe.SignatureVerificationError):
        raise ApiError(400, "bad_signature", "Invalid webhook signature.")
    if event["type"] == "checkout.session.completed":
        obj = event["data"]["object"]
        row = db.one("SELECT id FROM bookings WHERE public_id = :p", {"p": obj["client_reference_id"]})
        if row:
            db.call("ConfirmBooking", [row["id"], "stripe", obj["payment_intent"] or obj["id"]])
            cache.bump("listings")
    return jsonify(received=True)


@bp.post("/bookings/<public_id>/cancel")
@login_required
def cancel(public_id):
    b = _booking(public_id)
    role = "admin" if "admin" in g.user["roles"] and g.user["id"] not in (b["guest_id"], b["host_id"]) else "user"
    result = db.call("CancelBooking", [b["id"], g.user["id"], role])[0]
    cache.bump("listings")
    return jsonify(status="cancelled", **result)


@bp.post("/bookings/<public_id>/review")
@login_required
@limiter.limit("10 per hour")
def review(public_id):
    data = body(ReviewIn)
    b = _booking(public_id)
    if b["guest_id"] != g.user["id"]:
        raise ApiError(403, "forbidden", "Only the guest can review a stay.")
    # trg_reviews_bi enforces "completed stay by this guest"; the UNIQUE key enforces one review per stay.
    db.execute("""INSERT INTO reviews (booking_id, listing_id, author_id, rating, comment)
                  VALUES (:b, :l, :a, :r, :c)""",
               {"b": b["id"], "l": b["listing_id"], "a": g.user["id"], "r": data.rating, "c": data.comment})
    cache.bump("listings")
    return jsonify(reviewed=True), 201


@bp.post("/reviews/<int:review_id>/reply")
@login_required
def reply(review_id):
    data = body(ReplyIn)
    count, _ = db.execute(
        """UPDATE reviews r JOIN listings l ON l.id = r.listing_id SET r.host_reply = :t
           WHERE r.id = :id AND l.host_id = :u AND r.host_reply IS NULL""",
        {"t": data.reply, "id": review_id, "u": g.user["id"]})
    if not count:
        raise ApiError(404, "not_found", "Review not found or already answered.")
    return jsonify(replied=True)


def listing_reviews(listing_id, limit=12):
    rows = db.query(
        """SELECT r.id, r.rating, r.comment, r.host_reply, r.created_at, p.display_name AS author_name,
                  p.avatar_url AS author_avatar
           FROM reviews r JOIN user_profiles p ON p.user_id = r.author_id
           WHERE r.listing_id = :l AND r.hidden_at IS NULL
           ORDER BY r.created_at DESC LIMIT :n""", {"l": listing_id, "n": limit}, read=True)
    for r in rows:
        r["author"] = {"name": r.pop("author_name"), "avatar_url": r.pop("author_avatar")}
    return rows

