import io
import json

from PIL import Image

from app import db

LISTING = {
    "title": "Sunny loft near the river",
    "description": "A bright loft with tall windows, a workspace and a quiet bedroom away from the street.",
    "listing_mode": "short_term_stay", "property_type": "loft", "bedrooms": 1, "bathrooms": 1, "max_guests": 2,
    "size_sqft": 700, "price": 120, "amenities": ["wifi", "kitchen"],
    "address": {"street": "12 River Rd", "city": "Porto", "country": "PT", "lat": 41.14, "lng": -8.61},
}


def jpeg_with_gps():
    img = Image.new("RGB", (800, 600), "teal")
    exif = Image.Exif()
    exif[0x010F] = "SecretCam"  # Make
    exif[0x8825] = {2: (51.0, 30.0, 0.0)}  # GPS IFD
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    buf.seek(0)
    return buf


def test_admin_console_requires_admin_role(make_user):
    assert make_user(roles=("host", "guest")).get("/admin/kpis").status_code == 403
    assert make_user(roles=("admin", "guest")).get("/admin/kpis").status_code == 200


def test_listing_lifecycle_with_moderation_and_audit(make_user, client, tmp_path, app):
    app.config["UPLOAD_DIR"] = str(tmp_path)
    host = make_user(roles=("host", "guest"))
    pid = host.post("/host/listings", json=LISTING).get_json()["public_id"]
    assert host.post(f"/host/listings/{pid}/status", json={"action": "submit"}).status_code == 422  # no photos

    up = host.c.post(f"/api/v1/host/listings/{pid}/photos", data={"file": (jpeg_with_gps(), "a.jpg")},
                     headers={"X-CSRF-Token": host.c.get_cookie("hn_csrf").value}, content_type="multipart/form-data")
    assert up.status_code == 201
    stored = tmp_path / up.get_json()["url"].removeprefix("/media/")
    reopened = Image.open(stored)
    assert reopened.format == "WEBP" and not reopened.getexif()  # metadata stripped

    assert host.post(f"/host/listings/{pid}/status", json={"action": "submit"}).get_json()["status"] == "pending_review"
    assert client.get(f"/listings/{pid}").status_code == 404  # not public until approved

    admin = make_user(roles=("admin", "guest"))
    assert pid in [l["public_id"] for l in admin.get("/admin/listings").get_json()]
    assert admin.post(f"/admin/listings/{pid}/moderate", json={"decision": "reject"}).status_code == 422
    assert admin.post(f"/admin/listings/{pid}/moderate", json={"decision": "approve"}).get_json()["status"] == "published"
    assert client.get(f"/listings/{pid}").status_code == 200

    lid = db.one("SELECT id FROM listings WHERE public_id = :p", {"p": pid})["id"]
    entry = db.one("""SELECT actor_id, old_data, new_data FROM audit_log WHERE entity = 'listing' AND entity_id = :l
                      ORDER BY id DESC LIMIT 1""", {"l": lid})
    assert entry["actor_id"] == admin.user_id  # trigger picked up @actor_id
    assert json.loads(entry["new_data"])["status"] == "published"


def test_optimistic_locking(make_user):
    host = make_user(roles=("host", "guest"))
    pid = host.post("/host/listings", json=LISTING).get_json()["public_id"]
    v = host.get(f"/host/listings/{pid}").get_json()["version"]
    assert host.put(f"/host/listings/{pid}", json={**LISTING, "price": 130, "version": v}).status_code == 200
    stale = host.put(f"/host/listings/{pid}", json={**LISTING, "price": 140, "version": v})
    assert stale.status_code == 409 and stale.get_json()["error"]["code"] == "version_conflict"


def test_hosts_cannot_touch_other_hosts_listings(make_user):
    a, b = make_user(roles=("host", "guest")), make_user(roles=("host", "guest"))
    pid = a.post("/host/listings", json=LISTING).get_json()["public_id"]
    assert b.get(f"/host/listings/{pid}").status_code == 404
    assert b.put(f"/host/listings/{pid}", json={**LISTING, "version": 1}).status_code == 404
    assert make_user().post("/host/listings", json=LISTING).status_code == 403  # plain guest


def test_audit_log_is_append_only(app):
    import pytest
    from sqlalchemy.exc import DBAPIError
    db.execute("INSERT INTO audit_log (action, entity) VALUES ('test', 'test')")
    with pytest.raises(DBAPIError, match="append-only"):
        db.execute("UPDATE audit_log SET action = 'tampered'")
    with pytest.raises(DBAPIError, match="append-only"):
        db.execute("DELETE FROM audit_log")


def test_encrypted_backup_round_trip(make_user, app, tmp_path):
    import os

    from app.backups import decrypt_stream
    from app.security.crypto import cipher
    from tests.conftest import TEST_URL

    app.config["BACKUP_DIR"] = str(tmp_path)
    app.config["BACKUP_DATABASE_URL"] = TEST_URL.replace("mysql+pymysql", "mysql").split("?")[0]
    admin = make_user(roles=("admin", "guest"))
    r = admin.post("/admin/backups")
    assert r.status_code == 202
    b = admin.get("/admin/backups").get_json()[0]
    assert b["status"] == "succeeded", b["error"]
    raw = (tmp_path / b["file_name"]).read_bytes()
    assert raw.startswith(b"HNBK1") and b"CREATE TABLE" not in raw
    out = io.BytesIO()
    decrypt_stream(io.BytesIO(raw), out, cipher().keyring)
    assert b"CREATE TABLE `listings`" in out.getvalue()
    # tampering with any byte makes decryption fail
    bad = bytearray(raw)
    bad[-5] ^= 1
    import pytest
    from cryptography.exceptions import InvalidTag
    with pytest.raises(InvalidTag):
        decrypt_stream(io.BytesIO(bytes(bad)), io.BytesIO(), cipher().keyring)
    assert os.path.getsize(tmp_path / b["file_name"]) == b["size_bytes"]
