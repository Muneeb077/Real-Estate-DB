"""
Public marketplace endpoints. No authentication: anyone can browse.
All reads go through v_public_listings, so unpublished or private data can't leak.
"""
from datetime import date
from typing import Literal, Optional

from flask import Blueprint, jsonify
from pydantic import Field, model_validator

from .. import db
from ..errors import ApiError
from ..extensions import cache, limiter
from .common import Strict, args, decode_cursor, fulltext_query, page

bp = Blueprint("listings", __name__, url_prefix="/api/v1")

Mode = Literal["sale", "long_term_rent", "short_term_stay"]
PropertyType = Literal["house", "apartment", "condo", "townhouse", "villa", "cabin", "studio", "loft"]

_CARD = ("public_id", "title", "listing_mode", "property_type", "bedrooms", "bathrooms", "max_guests", "size_sqft",
         "price", "currency", "price_unit", "city", "state", "country", "lat", "lng", "cover_url", "cover_thumb_url",
         "rating_avg", "review_count", "published_at")


def card_columns(alias="v"):
    return ", ".join(f"{alias}.{c}" for c in _CARD)


CARD_COLUMNS = card_columns()


class SearchParams(Strict):
    q: Optional[str] = Field(None, max_length=200)
    mode: Optional[Mode] = None
    type: Optional[PropertyType] = None
    city: Optional[str] = Field(None, max_length=80)
    min_price: Optional[float] = Field(None, ge=0)
    max_price: Optional[float] = Field(None, ge=0)
    beds: Optional[int] = Field(None, ge=0, le=20)
    baths: Optional[float] = Field(None, ge=0, le=20)
    guests: Optional[int] = Field(None, ge=1, le=50)
    amenities: Optional[str] = Field(None, max_length=400, pattern=r"^[a-z_]+(,[a-z_]+)*$")
    bbox: Optional[str] = Field(None, description="min_lat,min_lng,max_lat,max_lng")
    near: Optional[str] = Field(None, description="lat,lng")
    radius_km: Optional[float] = Field(None, gt=0, le=200)
    check_in: Optional[date] = None
    check_out: Optional[date] = None
    sort: Literal["newest", "price_asc", "price_desc", "rating"] = "newest"
    cursor: Optional[str] = Field(None, max_length=200)
    limit: int = Field(24, ge=1, le=100)

    @model_validator(mode="after")
    def check(self):
        if (self.check_in is None) != (self.check_out is None):
            raise ValueError("check_in and check_out go together")
        if self.check_in and self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")
        for name, n in (("bbox", 4), ("near", 2)):
            val = getattr(self, name)
            if val:
                try:
                    nums = [float(x) for x in val.split(",")]
                except ValueError:
                    raise ValueError(f"{name} must be comma-separated numbers")
                if len(nums) != n:
                    raise ValueError(f"{name} needs {n} numbers")
        return self


def _coords(value, n):
    return [float(x) for x in value.split(",")] if value else [None] * n


@bp.get("/listings")
@limiter.limit("120 per minute")
def search():
    p = args(SearchParams)
    min_lat, min_lng, max_lat, max_lng = _coords(p.bbox, 4)
    if p.bbox:
        # keep the box sane so a zoomed-out map can't request the whole planet
        min_lat, max_lat = max(min_lat, -85), min(max_lat, 85)
        min_lng, max_lng = max(min_lng, -180), min(max_lng, 180)
    near_lat, near_lng = _coords(p.near, 2)
    cursor_value, cursor_id = decode_cursor(p.cursor)

    key = f"search:{cache.version('listings')}:{sorted(p.model_dump(exclude_none=True).items())}"
    cached = cache.get(key)
    if cached is not None:
        return jsonify(cached)

    rows = db.call("SearchListings", [
        fulltext_query(p.q), p.mode, p.type, p.city, p.min_price, p.max_price, p.beds, p.baths, p.guests,
        p.amenities, min_lat, min_lng, max_lat, max_lng, near_lat, near_lng, p.radius_km,
        p.check_in, p.check_out, p.sort, cursor_value, cursor_id, p.limit + 1,
    ], read=True)
    result = page(rows, p.limit)
    cache.set(key, result)
    return jsonify(result)


@bp.get("/listings/<public_id>")
def detail(public_id):
    listing = db.one(
        f"""SELECT v.id, {CARD_COLUMNS}, l.description, l.status, v.host_id, s.views
            FROM v_public_listings v
            JOIN listings l ON l.id = v.id
            JOIN listing_stats s ON s.listing_id = v.id
            WHERE v.public_id = :pid""",
        {"pid": public_id}, read=True,
    )
    if not listing:
        raise ApiError(404, "not_found", "Listing not found.")
    lid, host_id = listing.pop("id"), listing.pop("host_id")
    listing["photos"] = db.query(
        "SELECT id, url, thumb_url, alt FROM listing_photos WHERE listing_id = :id ORDER BY sort_order, id",
        {"id": lid}, read=True)
    listing["amenities"] = db.query(
        """SELECT a.code, a.label, a.category FROM listing_amenities la JOIN amenities a ON a.id = la.amenity_id
           WHERE la.listing_id = :id ORDER BY a.category, a.label""", {"id": lid}, read=True)
    listing["host"] = host_card(host_id)
    listing["reviews"] = listing_reviews(lid)
    return jsonify(listing)


def host_card(host_id):
    return db.one(
        """SELECT u.public_id, p.display_name AS name, p.avatar_url,
                  (h.verification_status = 'verified') AS verified, DATE(u.created_at) AS member_since
           FROM users u JOIN user_profiles p ON p.user_id = u.id
           LEFT JOIN host_profiles h ON h.user_id = u.id
           WHERE u.id = :id""", {"id": host_id}, read=True)


def listing_reviews(listing_id):
    # reviews arrive with the stays migration (0004); until then a listing has none
    return []


@bp.post("/listings/<public_id>/views")
@limiter.limit("30 per minute")
def record_view(public_id):
    db.execute("""UPDATE listing_stats s JOIN listings l ON l.id = s.listing_id
                  SET s.views = s.views + 1 WHERE l.public_id = :pid AND l.status = 'published'""",
               {"pid": public_id})
    return "", 204


@bp.get("/amenities")
def amenities():
    rows = cache.get("amenities")
    if rows is None:
        rows = db.query("SELECT code, label, category FROM amenities ORDER BY category, label", read=True)
        cache.set("amenities", rows, ttl=3600)
    return jsonify(rows)


@bp.get("/destinations")
def destinations():
    """
    Popular cities per mode for the home page, ranked with a window function.
    """
    key = f"destinations:{cache.version('listings')}"
    rows = cache.get(key)
    if rows is None:
        rows = db.query(
            """WITH per_city AS (
                   SELECT city, country, listing_mode, COUNT(*) AS listings, ROUND(AVG(price)) AS avg_price,
                          MIN(cover_thumb_url) AS image
                   FROM v_public_listings GROUP BY city, country, listing_mode
               )
               SELECT * FROM (
                   SELECT per_city.*, RANK() OVER (PARTITION BY listing_mode ORDER BY listings DESC, city) AS rnk
                   FROM per_city
               ) ranked WHERE rnk <= 8 ORDER BY listing_mode, rnk""", read=True)
        cache.set(key, rows, ttl=600)
    return jsonify(rows)


@bp.get("/hosts/<public_id>")
def host_profile(public_id):
    host = db.one(
        """SELECT u.id, u.public_id, p.display_name AS name, p.avatar_url, p.bio, h.agency_name,
                  (h.verification_status = 'verified') AS verified, DATE(u.created_at) AS member_since
           FROM users u JOIN user_profiles p ON p.user_id = u.id
           JOIN host_profiles h ON h.user_id = u.id
           WHERE u.public_id = :pid AND u.status = 'active'""", {"pid": public_id}, read=True)
    if not host:
        raise ApiError(404, "not_found", "Host not found.")
    hid = host.pop("id")
    host["stats"] = db.one(
        """SELECT COUNT(*) AS listings, ROUND(AVG(rating_avg), 2) AS rating_avg, SUM(review_count) AS reviews
           FROM v_public_listings WHERE host_id = :id""", {"id": hid}, read=True)
    host["listings"] = db.query(
        f"SELECT {CARD_COLUMNS} FROM v_public_listings v WHERE host_id = :id ORDER BY published_at DESC LIMIT 12",
        {"id": hid}, read=True)
    return jsonify(host)
