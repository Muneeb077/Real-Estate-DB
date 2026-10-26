from app import db
from app.security import crypto


def test_unverified_users_cannot_contact_hosts(make_user, make_listing):
    host = make_user(roles=("host", "guest"))
    listing = make_listing(host.user_id, mode="sale", price=500000)
    guest = make_user(verified=False)
    r = guest.post(f"/listings/{listing['public_id']}/offers", json={"amount": 480000})
    assert r.status_code == 403 and r.get_json()["error"]["code"] == "email_unverified"


def test_messages_are_encrypted_at_rest(make_user, make_listing):
    host = make_user(roles=("host", "guest"))
    listing = make_listing(host.user_id)
    guest = make_user()
    r = guest.post(f"/listings/{listing['public_id']}/conversations", json={"message": "Is parking included?"})
    assert r.status_code == 201
    raw = db.one("SELECT body_enc FROM messages ORDER BY id DESC LIMIT 1")["body_enc"]
    assert b"parking" not in bytes(raw)
    conv = host.get("/conversations").get_json()[0]
    assert conv["last_message"] == "Is parking included?" and conv["unread"] is True


def test_accept_offer_is_atomic_and_supersedes_others(make_user, make_listing):
    host = make_user(roles=("host", "guest"))
    listing = make_listing(host.user_id, mode="sale", price=500000)
    a, b = make_user(), make_user()
    oa = a.post(f"/listings/{listing['public_id']}/offers", json={"amount": 490000}).get_json()["public_id"]
    ob = b.post(f"/listings/{listing['public_id']}/offers", json={"amount": 470000}).get_json()["public_id"]

    assert a.post(f"/offers/{oa}/accept").status_code == 404  # guests can't accept
    r = host.post(f"/offers/{oa}/accept")
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["transaction"]["commission"] == 24500.0  # 5% host rate

    assert db.one("SELECT status FROM listings WHERE id = :id", {"id": listing["id"]})["status"] == "sold"
    statuses = {o["public_id"]: o["status"] for o in host.get("/host/offers").get_json()}
    assert statuses == {oa: "accepted", ob: "superseded"}
    # second accept fails inside the procedure with a readable message
    r = host.post(f"/offers/{ob}/accept")
    assert r.status_code == 409 and "no longer pending" in r.get_json()["error"]["message"]


def test_favorites_toggle_and_counter_trigger(make_user, make_listing):
    host = make_user(roles=("host", "guest"))
    listing = make_listing(host.user_id)
    guest = make_user()
    assert guest.put(f"/me/favorites/{listing['public_id']}").status_code == 204
    assert guest.put(f"/me/favorites/{listing['public_id']}").status_code == 204  # idempotent
    assert guest.get("/me/favorites/ids").get_json() == [listing["public_id"]]
    assert db.one("SELECT favorites FROM listing_stats WHERE listing_id = :id", {"id": listing["id"]})["favorites"] == 1
    assert guest.delete(f"/me/favorites/{listing['public_id']}").status_code == 204
    assert db.one("SELECT favorites FROM listing_stats WHERE listing_id = :id", {"id": listing["id"]})["favorites"] == 0


def test_phone_is_encrypted_with_blind_index(make_user):
    u = make_user()
    assert u.patch("/me/profile", json={"phone": "+1 555 0100"}).get_json()["phone"] == "+15550100"
    row = db.one("SELECT phone_enc, phone_hash FROM user_profiles WHERE user_id = :u", {"u": u.user_id})
    assert b"5550100" not in bytes(row["phone_enc"])
    assert bytes(row["phone_hash"]) == crypto.blind_index("+15550100", "user_profiles.phone")


def test_unknown_fields_are_rejected(make_user):
    u = make_user()
    r = u.patch("/me/profile", json={"display_name": "Ok", "role": "admin"})
    assert r.status_code == 422


def test_saved_search_alert_finds_new_listings(make_user, make_listing, monkeypatch):
    from app.alerts import run_saved_search_alerts
    guest = make_user()
    r = guest.post("/me/saved-searches", json={"name": "Alertville stays", "query": {"city": "Alertville", "mode": "short_term_stay"}})
    assert r.status_code == 201
    db.execute("UPDATE saved_searches SET last_notified_at = NOW() - INTERVAL 1 DAY WHERE user_id = :u", {"u": guest.user_id})
    host = make_user(roles=("host", "guest"))
    listing = make_listing(host.user_id, city="Alertville")
    db.execute("UPDATE listings SET published_at = NOW() WHERE id = :id", {"id": listing["id"]})
    sent = []
    monkeypatch.setattr("app.alerts.enqueue", lambda f, to, subject, text: sent.append((to, text)))
    assert run_saved_search_alerts() >= 1
    assert any(to == guest.email and listing["public_id"] in text for to, text in sent)
    sent.clear()
    run_saved_search_alerts()
    assert not [s for s in sent if s[0] == guest.email]  # nothing new the second time
