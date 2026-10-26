from app import db
from app.security import crypto

from .conftest import PASSWORD


def test_csrf_required_for_unsafe_requests(app):
    c = app.test_client()
    r = c.post("/api/v1/auth/login", json={"email": "a@b.dev", "password": "x"})
    assert r.status_code == 403
    assert r.get_json()["error"]["code"] == "csrf_failed"


def test_signup_stores_only_hashes_and_ciphertext(client):
    r = client.post("/auth/signup", json={"email": "Alice@Example.dev", "password": PASSWORD, "display_name": "Alice"})
    assert r.status_code == 201, r.get_json()
    assert r.get_json()["email"] == "alice@example.dev"
    row = db.one("SELECT email_enc, password_hash FROM users WHERE email_hash = :h",
                 {"h": crypto.blind_index("alice@example.dev", "users.email")})
    assert b"alice" not in bytes(row["email_enc"])
    assert row["password_hash"].startswith("$argon2id$")
    assert crypto.decrypt(row["email_enc"], "users.email") == "alice@example.dev"


def test_signup_rejects_weak_password_and_duplicates(client):
    assert client.post("/auth/signup", json={"email": "w@x.dev", "password": "short", "display_name": "W"}).status_code == 422
    ok = {"email": "dup@x.dev", "password": PASSWORD, "display_name": "Dup"}
    assert client.post("/auth/signup", json=ok).status_code == 201
    assert client.post("/auth/signup", json=ok).status_code == 409


def test_login_lockout_after_repeated_failures(client, make_user):
    u = make_user()
    for _ in range(5):
        assert client.post("/auth/login", json={"email": u.email, "password": "wrong-Password-1"}).status_code == 401
    r = client.post("/auth/login", json={"email": u.email, "password": PASSWORD})
    assert r.status_code == 429


def test_refresh_rotation_and_reuse_detection(make_user):
    u = make_user()
    old = u.c.get_cookie("hn_refresh", path="/api/v1/auth").value
    assert u.post("/auth/refresh").status_code == 200
    new = u.c.get_cookie("hn_refresh", path="/api/v1/auth").value
    assert new != old
    # replaying the old (rotated) token revokes the whole family, including the new one
    u.c.set_cookie("hn_refresh", old, path="/api/v1/auth")
    assert u.post("/auth/refresh").status_code == 401
    u.c.set_cookie("hn_refresh", new, path="/api/v1/auth")
    assert u.post("/auth/refresh").status_code == 401


def test_password_reset_token_is_single_use(client, make_user, monkeypatch):
    u = make_user()
    sent = {}
    monkeypatch.setattr("app.api.auth.enqueue", lambda f, to, subject, text: sent.update(text=text))
    assert client.post("/auth/forgot-password", json={"email": u.email}).status_code == 202
    token = sent["text"].split("token=")[1].split()[0]
    stored = db.one("SELECT token_hash FROM auth_tokens WHERE purpose = 'reset_password' ORDER BY id DESC LIMIT 1")
    assert bytes(stored["token_hash"]) == crypto.sha256(token)  # only the hash is stored
    new_pw = "Brand-new-pass-77"
    assert client.post("/auth/reset-password", json={"token": token, "password": new_pw}).status_code == 200
    assert client.post("/auth/reset-password", json={"token": token, "password": new_pw}).status_code == 400
    assert client.post("/auth/login", json={"email": u.email, "password": new_pw}).status_code == 200


def test_forgot_password_does_not_reveal_accounts(client):
    r = client.post("/auth/forgot-password", json={"email": "nobody@nowhere.dev"})
    assert r.status_code == 202
