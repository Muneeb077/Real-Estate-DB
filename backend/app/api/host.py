"""
Host features: onboarding, listing management (optimistic locking), photos,
calendar (blocked dates, price rules) and the earnings dashboard.
"""
import json
from datetime import date
from typing import Literal, Optional

from flask import Blueprint, g, jsonify, request
from pydantic import Field, model_validator
from ulid import ULID

from .. import db, storage
from ..errors import ApiError
from ..extensions import cache
from ..security import crypto
from ..security.rbac import host_required, verified_required
from .common import Strict, body

bp = Blueprint("host", __name__, url_prefix="/api/v1/host")


class OnboardingIn(Strict):
    agency_name: Optional[str] = Field(None, max_length=150)
    license_number: Optional[str] = Field(None, max_length=60)
    phone: str = Field(pattern=r"^\+?[0-9 ()-]{7,20}$")


@bp.post("/onboarding")
@verified_required
def onboarding():
    """
    Turns a guest into a host. License number and phone are encrypted; an admin
    verifies the host before the verified badge appears.
    """
    data = body(OnboardingIn)
    if "host" in g.user["roles"]:
        raise ApiError(409, "already_host", "You're already a host.")
    phone = "".join(c for c in data.phone if c.isdigit() or c == "+")
    with db.transaction() as conn:
        db.execute(
            """INSERT INTO host_profiles (user_id, agency_name, license_enc, verification_status)
               VALUES (:u, :a, :l, :s)""",
            {"u": g.user["id"], "a": data.agency_name,
             "l": crypto.encrypt(data.license_number, "host_profiles.license") if data.license_number else None,
             "s": "pending" if data.license_number else "unverified"}, conn=conn)
        db.execute("INSERT INTO user_roles (user_id, role) VALUES (:u, 'host')", {"u": g.user["id"]}, conn=conn)
        db.execute("UPDATE user_profiles SET phone_enc = :pe, phone_hash = :ph WHERE user_id = :u",
                   {"pe": crypto.encrypt(phone, "user_profiles.phone"),
                    "ph": crypto.blind_index(phone, "user_profiles.phone"), "u": g.user["id"]}, conn=conn)
    return jsonify(host=True), 201


# ---------------------------------------------------------------- listings

Mode = Literal["sale", "long_term_rent", "short_term_stay"]
PropertyType = Literal["house", "apartment", "condo", "townhouse", "villa", "cabin", "studio", "loft"]
UNIT = {"sale": "total", "long_term_rent": "month", "short_term_stay": "night"}


class AddressIn(Strict):
    street: str = Field(min_length=3, max_length=200)
    city: str = Field(min_length=2, max_length=80)
    state: Optional[str] = Field(None, max_length=80)
    postal_code: Optional[str] = Field(None, max_length=16)
    country: str = Field(min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    lat: float = Field(ge=-85, le=85)
    lng: float = Field(ge=-180, le=180)


class ListingIn(Strict):
    title: str = Field(min_length=10, max_length=140)
    description: str = Field(min_length=50, max_length=5000)
    listing_mode: Mode
    property_type: PropertyType
    bedrooms: int = Field(ge=0, le=30)
    bathrooms: float = Field(ge=0.5, le=30)
    max_guests: Optional[int] = Field(None, ge=1, le=50)
    size_sqft: Optional[int] = Field(None, ge=100, le=100000)
    price: float = Field(gt=0, le=1_000_000_000)
    currency: str = Field("USD", pattern=r"^[A-Z]{3}$")
    amenities: list[str] = Field(default_factory=list, max_length=40)
    address: AddressIn

    @model_validator(mode="after")
    def stays_need_guests(self):
        if self.listing_mode == "short_term_stay" and not self.max_guests:
            raise ValueError("max_guests is required for stays")
        return self


class ListingUpdate(ListingIn):
    version: int


class StatusIn(Strict):
    action: Literal["submit", "pause", "resume", "archive"]


class PhotoOrderIn(Strict):
    photo_ids: list[int] = Field(min_length=1, max_length=50)


class CalendarIn(Strict):
    block: list[date] = Field(default_factory=list, max_length=366)
    unblock: list[date] = Field(default_factory=list, max_length=366)


class PriceRuleIn(Strict):
    label: str = Field(min_length=2, max_length=60)
    start_date: date
    end_date: date
    nightly_price: float = Field(gt=0, le=100000)
    weekends_only: bool = False

    @model_validator(mode="after")
    def order(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


def _own_listing(public_id, conn=None, lock=False):
    row = db.one(f"""SELECT id, public_id, status, version, address_id, listing_mode FROM listings
                     WHERE public_id = :p AND host_id = :h AND deleted_at IS NULL {"FOR UPDATE" if lock else ""}""",
                 {"p": public_id, "h": g.user["id"]}, conn=conn)
    if not row:
        raise ApiError(404, "not_found", "Listing not found.")
    return row


def _point(addr):
    return f"POINT({addr.lat:.6f} {addr.lng:.6f})"


def _set_amenities(listing_id, codes, conn):
    db.execute("DELETE FROM listing_amenities WHERE listing_id = :l", {"l": listing_id}, conn=conn)
    if codes:
        db.execute("""INSERT INTO listing_amenities (listing_id, amenity_id)
                      SELECT :l, id FROM amenities WHERE JSON_CONTAINS(:codes, JSON_QUOTE(code))""",
                   {"l": listing_id, "codes": json.dumps(sorted(set(codes)))}, conn=conn)


@bp.get("/listings")
@host_required
def my_listings():
    return jsonify(db.query(
        """SELECT l.public_id, l.title, l.listing_mode, l.status, l.price, l.price_unit, l.currency, l.city,
                  l.moderation_note, l.updated_at, s.views, s.favorites, s.rating_avg, s.review_count,
                  (SELECT p.thumb_url FROM listing_photos p WHERE p.listing_id = l.id ORDER BY p.sort_order LIMIT 1) AS thumb
           FROM listings l JOIN listing_stats s ON s.listing_id = l.id
           WHERE l.host_id = :h AND l.deleted_at IS NULL
           ORDER BY l.updated_at DESC LIMIT 500""", {"h": g.user["id"]}))


@bp.get("/listings/<public_id>")
@host_required
def get_listing(public_id):
    own = _own_listing(public_id)
    row = db.one(
        """SELECT l.public_id, l.title, l.description, l.listing_mode, l.property_type, l.bedrooms, l.bathrooms,
                  l.max_guests, l.size_sqft, l.price, l.currency, l.status, l.version, l.moderation_note,
                  a.street_enc, a.city, a.state, a.postal_code, a.country,
                  ST_Latitude(a.location) AS lat, ST_Longitude(a.location) AS lng
           FROM listings l JOIN addresses a ON a.id = l.address_id WHERE l.id = :id""", {"id": own["id"]})
    street = crypto.decrypt(row.pop("street_enc"), "addresses.street") if row["street_enc"] else ""
    row["address"] = {"street": street, **{k: row.pop(k) for k in ("city", "state", "postal_code", "country", "lat", "lng")}}
    row["amenities"] = [r["code"] for r in db.query(
        "SELECT a.code FROM listing_amenities la JOIN amenities a ON a.id = la.amenity_id WHERE la.listing_id = :l",
        {"l": own["id"]})]
    row["photos"] = db.query("SELECT id, url, thumb_url, alt, sort_order FROM listing_photos WHERE listing_id = :l "
                             "ORDER BY sort_order, id", {"l": own["id"]})
    row["blocked_dates"] = [r["day"] for r in db.query(
        "SELECT day FROM blocked_dates WHERE listing_id = :l AND day >= CURDATE() ORDER BY day", {"l": own["id"]})]
    row["price_rules"] = db.query("SELECT id, label, start_date, end_date, nightly_price, weekends_only FROM price_rules "
                                  "WHERE listing_id = :l ORDER BY start_date", {"l": own["id"]})
    return jsonify(row)


@bp.post("/listings")
@host_required
def create_listing():
    data = body(ListingIn)
    a = data.address
    pid = str(ULID())
    with db.transaction() as conn:
        _, aid = db.execute(
            """INSERT INTO addresses (street_enc, city, state, postal_code, country, location)
               VALUES (:s, :c, :st, :pc, :co, ST_GeomFromText(:pt, 4326))""",
            {"s": crypto.encrypt(a.street, "addresses.street"), "c": a.city, "st": a.state, "pc": a.postal_code,
             "co": a.country, "pt": _point(a)}, conn=conn)
        _, lid = db.execute(
            """INSERT INTO listings (public_id, host_id, address_id, title, description, listing_mode, property_type,
                                     bedrooms, bathrooms, max_guests, size_sqft, price, currency, price_unit, status)
               VALUES (:p, :h, :a, :t, :d, :m, :pt, :b, :ba, :g, :sz, :pr, :cur, :u, 'draft')""",
            {"p": pid, "h": g.user["id"], "a": aid, "t": data.title, "d": data.description, "m": data.listing_mode,
             "pt": data.property_type, "b": data.bedrooms, "ba": data.bathrooms,
             "g": data.max_guests if data.listing_mode == "short_term_stay" else None, "sz": data.size_sqft,
             "pr": data.price, "cur": data.currency, "u": UNIT[data.listing_mode]}, conn=conn)
        _set_amenities(lid, data.amenities, conn)
    return jsonify(public_id=pid, status="draft"), 201


@bp.put("/listings/<public_id>")
@host_required
def update_listing(public_id):
    """
    Optimistic locking: the client sends the version it loaded. If someone else
    saved in between (another tab, a co-host, an admin), the UPDATE matches no
    row and the client is told to reload instead of silently overwriting.
    """
    data = body(ListingUpdate)
    a = data.address
    with db.transaction() as conn:
        own = _own_listing(public_id, conn)
        count, _ = db.execute(
            """UPDATE listings SET title = :t, description = :d, listing_mode = :m, property_type = :pt,
                      bedrooms = :b, bathrooms = :ba, max_guests = :g, size_sqft = :sz, price = :pr, currency = :cur,
                      price_unit = :u
               WHERE id = :id AND version = :v""",
            {"t": data.title, "d": data.description, "m": data.listing_mode, "pt": data.property_type,
             "b": data.bedrooms, "ba": data.bathrooms,
             "g": data.max_guests if data.listing_mode == "short_term_stay" else None, "sz": data.size_sqft,
             "pr": data.price, "cur": data.currency, "u": UNIT[data.listing_mode], "id": own["id"], "v": data.version},
            conn=conn)
        if count == 0:
            raise ApiError(409, "version_conflict", "This listing was changed elsewhere. Reload to see the latest version.")
        db.execute(
            """UPDATE addresses SET street_enc = :s, city = :c, state = :st, postal_code = :pc, country = :co,
                      location = ST_GeomFromText(:pt, 4326) WHERE id = :id""",
            {"s": crypto.encrypt(a.street, "addresses.street"), "c": a.city, "st": a.state, "pc": a.postal_code,
             "co": a.country, "pt": _point(a), "id": own["address_id"]}, conn=conn)
        _set_amenities(own["id"], data.amenities, conn)
        version = db.scalar("SELECT version FROM listings WHERE id = :id", {"id": own["id"]}, conn=conn)
    cache.bump("listings")
    return jsonify(public_id=public_id, version=version)


@bp.post("/listings/<public_id>/status")
@host_required
def change_status(public_id):
    action = body(StatusIn).action
    with db.transaction() as conn:
        own = _own_listing(public_id, conn, lock=True)
        current = own["status"]
        if action == "submit":
            if current not in ("draft", "rejected", "paused"):
                raise ApiError(409, "bad_transition", "Only drafts, paused or rejected listings can be submitted.")
            if not db.scalar("SELECT COUNT(*) FROM listing_photos WHERE listing_id = :l", {"l": own["id"]}, conn=conn):
                raise ApiError(422, "photos_required", "Add at least one photo before submitting.")
            review = db.scalar("SELECT JSON_UNQUOTE(v) FROM settings WHERE k = 'new_listings_require_review'",
                               conn=conn) == "true"
            new = "pending_review" if review and current != "paused" else "published"
        elif action == "pause":
            if current != "published":
                raise ApiError(409, "bad_transition", "Only published listings can be paused.")
            new = "paused"
        elif action == "resume":
            if current != "paused":
                raise ApiError(409, "bad_transition", "Only paused listings can be resumed.")
            new = "published"
        else:
            if db.scalar("""SELECT COUNT(*) FROM bookings WHERE listing_id = :l AND status = 'confirmed'
                            AND check_out > CURDATE()""", {"l": own["id"]}, conn=conn):
                raise ApiError(409, "upcoming_bookings", "Cancel or finish upcoming stays before archiving.")
            new = "archived"
        db.execute("UPDATE listings SET status = :s, moderation_note = IF(:s = 'pending_review', NULL, moderation_note) "
                   "WHERE id = :id", {"s": new, "id": own["id"]}, conn=conn)
    cache.bump("listings")
    return jsonify(status=new)


@bp.post("/listings/<public_id>/photos")
@host_required
def upload_photo(public_id):
    own = _own_listing(public_id)
    f = request.files.get("file")
    if not f:
        raise ApiError(400, "no_file", "Attach an image as 'file'.")
    if db.scalar("SELECT COUNT(*) FROM listing_photos WHERE listing_id = :l", {"l": own["id"]}) >= 30:
        raise ApiError(409, "too_many_photos", "A listing can have up to 30 photos.")
    full, thumb = storage.process_image(f)
    url, thumb_url = storage.save(public_id, full, thumb)
    _, pid = db.execute(
        """INSERT INTO listing_photos (listing_id, url, thumb_url, alt, sort_order)
           SELECT :l, :u, :t, :a, COALESCE(MAX(sort_order) + 1, 0) FROM listing_photos WHERE listing_id = :l""",
        {"l": own["id"], "u": url, "t": thumb_url, "a": (request.form.get("alt") or "")[:200] or None})
    cache.bump("listings")
    return jsonify(id=pid, url=url, thumb_url=thumb_url), 201


@bp.delete("/listings/<public_id>/photos/<int:photo_id>")
@host_required
def delete_photo(public_id, photo_id):
    own = _own_listing(public_id)
    with db.transaction() as conn:
        db.execute("DELETE FROM listing_photos WHERE id = :p AND listing_id = :l", {"p": photo_id, "l": own["id"]}, conn=conn)
        _renumber_photos(own["id"], conn)
    cache.bump("listings")
    return "", 204


def _renumber_photos(listing_id, conn, order=None):
    # keeps sort_order dense from 0, which v_public_listings relies on for the cover photo
    ids = order or [r["id"] for r in db.query(
        "SELECT id FROM listing_photos WHERE listing_id = :l ORDER BY sort_order, id", {"l": listing_id}, conn=conn)]
    for i, pid in enumerate(ids):
        db.execute("UPDATE listing_photos SET sort_order = :o WHERE id = :p AND listing_id = :l",
                   {"o": i, "p": pid, "l": listing_id}, conn=conn)


@bp.put("/listings/<public_id>/photos/order")
@host_required
def reorder_photos(public_id):
    data = body(PhotoOrderIn)
    own = _own_listing(public_id)
    with db.transaction() as conn:
        existing = {r["id"] for r in db.query("SELECT id FROM listing_photos WHERE listing_id = :l", {"l": own["id"]}, conn=conn)}
        if set(data.photo_ids) != existing:
            raise ApiError(422, "bad_order", "Send every photo id of this listing exactly once.")
        _renumber_photos(own["id"], conn, data.photo_ids)
    cache.bump("listings")
    return "", 204


@bp.put("/listings/<public_id>/calendar")
@host_required
def update_calendar(public_id):
    data = body(CalendarIn)
    own = _own_listing(public_id)
    with db.transaction() as conn:
        for day in data.block:
            db.execute("INSERT IGNORE INTO blocked_dates (listing_id, day) VALUES (:l, :d)", {"l": own["id"], "d": day}, conn=conn)
        for day in data.unblock:
            db.execute("DELETE FROM blocked_dates WHERE listing_id = :l AND day = :d", {"l": own["id"], "d": day}, conn=conn)
    cache.bump("listings")
    return "", 204


@bp.post("/listings/<public_id>/price-rules")
@host_required
def add_price_rule(public_id):
    data = body(PriceRuleIn)
    own = _own_listing(public_id)
    _, rid = db.execute(
        """INSERT INTO price_rules (listing_id, label, start_date, end_date, nightly_price, weekends_only)
           VALUES (:l, :lab, :s, :e, :p, :w)""",
        {"l": own["id"], "lab": data.label, "s": data.start_date, "e": data.end_date, "p": data.nightly_price,
         "w": data.weekends_only})
    return jsonify(id=rid), 201


@bp.delete("/listings/<public_id>/price-rules/<int:rule_id>")
@host_required
def delete_price_rule(public_id, rule_id):
    own = _own_listing(public_id)
    db.execute("DELETE FROM price_rules WHERE id = :r AND listing_id = :l", {"r": rule_id, "l": own["id"]})
    return "", 204


# ---------------------------------------------------------------- dashboard

@bp.get("/dashboard")
@host_required
def dashboard():
    hid = g.user["id"]
    summary = db.one(
        """SELECT
             (SELECT COUNT(*) FROM listings WHERE host_id = :h AND status = 'published') AS published,
             (SELECT COUNT(*) FROM listings WHERE host_id = :h AND status IN ('draft','pending_review','rejected')) AS in_progress,
             (SELECT COUNT(*) FROM bookings WHERE host_id = :h AND status = 'confirmed' AND check_in >= CURDATE()) AS upcoming_stays,
             (SELECT COUNT(*) FROM offers o JOIN listings l ON l.id = o.listing_id WHERE l.host_id = :h AND o.status = 'pending') AS pending_offers,
             (SELECT COUNT(*) FROM viewings v JOIN listings l ON l.id = v.listing_id WHERE l.host_id = :h AND v.status = 'requested') AS pending_viewings,
             (SELECT ROUND(AVG(s.rating_avg), 2) FROM listing_stats s JOIN listings l ON l.id = s.listing_id
               WHERE l.host_id = :h AND s.rating_avg IS NOT NULL) AS rating_avg,
             (SELECT COALESCE(SUM(amount - refunded - service_fee - commission), 0) FROM transactions
               WHERE host_id = :h AND created_at >= DATE_FORMAT(CURDATE(), '%Y-%m-01')) AS payout_this_month,
             (SELECT verification_status FROM host_profiles WHERE user_id = :h) AS verification""",
        {"h": hid}, read=True)
    upcoming = db.query(
        """SELECT b.public_id, b.check_in, b.check_out, b.guests, b.total_price, b.currency, l.title AS listing_title,
                  p.display_name AS guest_name
           FROM bookings b JOIN listings l ON l.id = b.listing_id JOIN user_profiles p ON p.user_id = b.guest_id
           WHERE b.host_id = :h AND b.status = 'confirmed' AND b.check_out >= CURDATE()
           ORDER BY b.check_in LIMIT 8""", {"h": hid}, read=True)
    return jsonify(
        summary=summary,
        earnings=db.call("HostEarnings", [hid], read=True),
        listings=db.call("HostListingPerformance", [hid], read=True)[:50],
        upcoming=upcoming,
    )
