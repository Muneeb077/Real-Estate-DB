"""
Tests run against a real MySQL database (procedures, triggers and events are the
point of the project, so they are not mocked). The database named in
TEST_DATABASE_URL is dropped and rebuilt with `alembic upgrade head` once per run.

    TEST_DATABASE_URL=mysql+pymysql://root@127.0.0.1:3306/homenest_test pytest
"""
import base64
import os
import secrets

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

TEST_URL = os.environ.get("TEST_DATABASE_URL", "mysql+pymysql://root@127.0.0.1:3307/homenest_test?charset=utf8mb4")

os.environ.update({
    "APP_ENV": "test",
    "DATABASE_URL": TEST_URL,
    "MIGRATION_DATABASE_URL": TEST_URL,
    "DATABASE_REPLICA_URL": "",
    "SECRET_KEY": secrets.token_hex(32),
    "KEK_KEYS": f"v1:{base64.b64encode(secrets.token_bytes(32)).decode()}",
    "KEK_ACTIVE": "v1",
    "BLIND_INDEX_KEY": base64.b64encode(secrets.token_bytes(32)).decode(),
    "COOKIE_SECURE": "false",
    "REDIS_URL": "",
    "SMTP_URL": "",
    "STRIPE_SECRET_KEY": "",
    "DB_SSL_REQUIRED": "false",
})


def _rebuild_database():
    url = make_url(TEST_URL)
    server = create_engine(url.set(database=""))
    with server.connect() as c:
        c.execute(text(f"DROP DATABASE IF EXISTS `{url.database}`"))
        c.execute(text(f"CREATE DATABASE `{url.database}` CHARACTER SET utf8mb4"))
    server.dispose()
    from alembic import command
    from alembic.config import Config as AlembicConfig
    here = os.path.dirname(os.path.dirname(__file__))
    cfg = AlembicConfig(os.path.join(here, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(here, "migrations"))
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def app():
    _rebuild_database()
    from app import create_app
    application = create_app({"TESTING": True, "REQUIRE_VERIFIED_EMAIL": True, "ADMIN_REQUIRE_MFA": True})
    with application.app_context():
        yield application


class ApiClient:
    """
    Test client that behaves like the frontend: sends the CSRF header on unsafe requests.
    """

    def __init__(self, app):
        self.c = app.test_client()
        self.c.get("/api/v1/auth/csrf")

    def _csrf(self):
        cookie = self.c.get_cookie("hn_csrf")
        return {"X-CSRF-Token": cookie.value if cookie else ""}

    def get(self, path, **kw):
        return self.c.get(f"/api/v1{path}", **kw)

    def post(self, path, json=None, **kw):
        return self.c.post(f"/api/v1{path}", json=json, headers=self._csrf(), **kw)

    def put(self, path, json=None, **kw):
        return self.c.put(f"/api/v1{path}", json=json, headers=self._csrf(), **kw)

    def patch(self, path, json=None, **kw):
        return self.c.patch(f"/api/v1{path}", json=json, headers=self._csrf(), **kw)

    def delete(self, path, json=None, **kw):
        return self.c.delete(f"/api/v1{path}", json=json, headers=self._csrf(), **kw)


@pytest.fixture
def client(app):
    return ApiClient(app)


PASSWORD = "Correct-horse-42"


@pytest.fixture
def make_user(app):
    """
    Creates a user directly in the database and returns a logged-in ApiClient.
    """
    from ulid import ULID

    from app import db
    from app.security import crypto
    from app.security.passwords import hash_password

    def _make(roles=("guest",), verified=True, email=None):
        email = email or f"user-{secrets.token_hex(4)}@test.dev"
        with db.transaction() as conn:
            _, uid = db.execute(
                """INSERT INTO users (public_id, email_enc, email_hash, email_verified_at, password_hash)
                   VALUES (:p, :e, :h, IF(:v, NOW(), NULL), :pw)""",
                {"p": str(ULID()), "e": crypto.encrypt(email, "users.email"),
                 "h": crypto.blind_index(email, "users.email"), "v": verified, "pw": hash_password(PASSWORD)},
                conn=conn)
            for r in roles:
                db.execute("INSERT INTO user_roles (user_id, role) VALUES (:u, :r)", {"u": uid, "r": r}, conn=conn)
            db.execute("INSERT INTO user_profiles (user_id, display_name) VALUES (:u, :n)",
                       {"u": uid, "n": email.split("@")[0]}, conn=conn)
            if "host" in roles:
                db.execute("INSERT INTO host_profiles (user_id, verification_status) VALUES (:u, 'verified')",
                           {"u": uid}, conn=conn)
        c = ApiClient(app)
        r = c.post("/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, r.get_json()
        c.user_id, c.email = uid, email
        return c

    return _make


@pytest.fixture
def make_listing(app):
    from ulid import ULID

    from app import db

    def _make(host_id, mode="short_term_stay", price=150, status="published", city="Lisbon", guests=4):
        unit = {"sale": "total", "long_term_rent": "month", "short_term_stay": "night"}[mode]
        with db.transaction() as conn:
            _, aid = db.execute(
                """INSERT INTO addresses (city, country, location)
                   VALUES (:c, 'PT', ST_GeomFromText('POINT(38.72 -9.14)', 4326))""", {"c": city}, conn=conn)
            pid = str(ULID())
            _, lid = db.execute(
                """INSERT INTO listings (public_id, host_id, address_id, title, description, listing_mode,
                                         property_type, bedrooms, bathrooms, max_guests, price, price_unit, status)
                   VALUES (:p, :h, :a, 'Test home', 'A lovely test home with a garden.', :m, 'apartment', 2, 1,
                           :g, :price, :u, :s)""",
                {"p": pid, "h": host_id, "a": aid, "m": mode, "g": guests if mode == "short_term_stay" else None,
                 "price": price, "u": unit, "s": status}, conn=conn)
        return {"id": lid, "public_id": pid}

    return _make
