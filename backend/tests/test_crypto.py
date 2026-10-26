import base64
import os

import pytest
from cryptography.exceptions import InvalidTag

from app import db
from app.keyrotation import key_usage, rotate
from app.security import crypto
from app.security.crypto import FieldCipher, LocalKeyring


def keyring(**keys):
    spec = ",".join(f"{k}:{base64.b64encode(v).decode()}" for k, v in keys.items())
    return spec


def test_round_trip_and_context_binding():
    c = FieldCipher(LocalKeyring(keyring(v1=os.urandom(32)), "v1"), base64.b64encode(os.urandom(32)).decode())
    blob = c.encrypt("+44 20 7946 0000", "user_profiles.phone")
    assert c.decrypt(blob, "user_profiles.phone") == "+44 20 7946 0000"
    assert c.encrypt("same", "x") != c.encrypt("same", "x")  # fresh DEK + nonce every time
    with pytest.raises(InvalidTag):
        c.decrypt(blob, "users.email")  # ciphertext moved to another column is rejected


def test_blind_index_is_deterministic_and_keyed():
    k1, k2 = base64.b64encode(os.urandom(32)).decode(), base64.b64encode(os.urandom(32)).decode()
    ring = LocalKeyring(keyring(v1=os.urandom(32)), "v1")
    a, b = FieldCipher(ring, k1), FieldCipher(ring, k2)
    assert a.blind_index(" Bob@X.dev ", "users.email") == a.blind_index("bob@x.dev", "users.email")
    assert a.blind_index("bob@x.dev", "users.email") != b.blind_index("bob@x.dev", "users.email")


def test_kek_rotation_rewraps_everything(app, make_user):
    make_user()
    old_spec, old_active = app.config["KEK_KEYS"], app.config["KEK_ACTIVE"]
    original = crypto.cipher()
    sample = db.one("SELECT id, email_enc FROM users ORDER BY id LIMIT 1")
    email = original.decrypt(sample["email_enc"], "users.email")

    new_ring = LocalKeyring(f"{old_spec},v2:{base64.b64encode(os.urandom(32)).decode()}", "v2")
    crypto._cipher = FieldCipher(new_ring, app.config["BLIND_INDEX_KEY"])
    try:
        assert rotate(log=lambda *_: None) > 0
        usage = key_usage()
        assert all(set(per_kid) <= {"v2"} for per_kid in usage.values())
        # v1 can now be retired: a keyring with only v2 still decrypts everything
        only_v2 = FieldCipher(LocalKeyring(new_ring_spec_v2(new_ring), "v2"), app.config["BLIND_INDEX_KEY"])
        row = db.one("SELECT email_enc FROM users WHERE id = :id", {"id": sample["id"]})
        assert only_v2.decrypt(row["email_enc"], "users.email") == email
    finally:
        # rotate back so later tests keep working with the original keyring
        crypto._cipher = FieldCipher(LocalKeyring(f"{old_spec},v2:{base64.b64encode(new_ring._keys['v2']).decode()}",
                                                  old_active), app.config["BLIND_INDEX_KEY"])
        rotate(log=lambda *_: None)
        crypto._cipher = original


def new_ring_spec_v2(ring):
    return f"v2:{base64.b64encode(ring._keys['v2']).decode()}"
