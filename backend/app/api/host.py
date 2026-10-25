"""
Host features: onboarding now; listing management and dashboards are added below.
"""
from typing import Optional

from flask import Blueprint, g, jsonify
from pydantic import Field

from .. import db
from ..errors import ApiError
from ..security import crypto
from ..security.rbac import verified_required
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
