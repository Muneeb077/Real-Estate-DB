import threading
from datetime import date, timedelta

from app import db


def d(n):
    return (date.today() + timedelta(days=n)).isoformat()


def test_quote_uses_price_rules(make_user, make_listing):
    host = make_user(roles=("host", "guest"))
    listing = make_listing(host.user_id, price=100)
    db.execute("""INSERT INTO price_rules (listing_id, label, start_date, end_date, nightly_price)
                  VALUES (:l, 'Peak', :s, :e, 250)""", {"l": listing["id"], "s": d(12), "e": d(13)})
    q = host.get(f"/listings/{listing['public_id']}/quote?check_in={d(10)}&check_out={d(15)}&guests=2").get_json()
    # nights 10,11 @100 + 12,13 @250 + 14 @100
    assert q["nights"] == 5 and q["subtotal"] == 800.0 and q["service_fee"] == 80.0 and q["total"] == 880.0
    assert q["available"] is True


def test_concurrent_overlapping_bookings_only_one_wins(app, make_user, make_listing):
    host = make_user(roles=("host", "guest"))
    listing = make_listing(host.user_id)
    guests = [make_user() for _ in range(4)]
    results = []

    def attempt(client, start):
        with app.app_context():
            r = client.post(f"/listings/{listing['public_id']}/bookings",
                            json={"check_in": d(start), "check_out": d(start + 3), "guests": 2})
            results.append(r.status_code)

    threads = [threading.Thread(target=attempt, args=(g, 20 + i)) for i, g in enumerate(guests)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # stays 20-23, 21-24, 22-25, 23-26 all overlap pairwise except (20-23, 23-26)
    assert results.count(201) in (1, 2)
    active = db.query("""SELECT check_in, check_out FROM bookings WHERE listing_id = :l AND status = 'pending'
                         ORDER BY check_in""", {"l": listing["id"]})
    for a, b in zip(active, active[1:]):
        assert a["check_out"] <= b["check_in"]  # no overlaps survived


def test_idempotency_key_returns_same_booking(make_user, make_listing):
    host = make_user(roles=("host", "guest"))
    listing = make_listing(host.user_id)
    guest = make_user()
    payload = {"check_in": d(40), "check_out": d(42), "guests": 1}
    a = guest.post(f"/listings/{listing['public_id']}/bookings", json=payload, headers={"Idempotency-Key": "k1"})
    b = guest.post(f"/listings/{listing['public_id']}/bookings", json=payload, headers={"Idempotency-Key": "k1"})
    assert a.status_code == 201 and b.status_code == 201
    assert a.get_json()["public_id"] == b.get_json()["public_id"]


def test_pay_confirm_reveals_address_and_cancel_refund_policy(make_user, make_listing):
    host = make_user(roles=("host", "guest"))
    listing = make_listing(host.user_id, price=100)
    guest = make_user()
    pid = guest.post(f"/listings/{listing['public_id']}/bookings",
                     json={"check_in": d(3), "check_out": d(5), "guests": 2}).get_json()["public_id"]
    assert "address" not in guest.get(f"/bookings/{pid}").get_json()
    assert guest.post(f"/bookings/{pid}/pay").get_json()["status"] == "confirmed"
    detail = guest.get(f"/bookings/{pid}").get_json()
    assert detail["status"] == "confirmed" and "address" in detail
    tx = db.one("SELECT amount, commission, service_fee FROM transactions WHERE booking_id = (SELECT id FROM bookings WHERE public_id = :p)",
                {"p": pid})
    assert tx == {"amount": 220.0, "commission": 10.0, "service_fee": 20.0}
    # guest cancels 3 days out: 50% of the nightly subtotal back
    r = guest.post(f"/bookings/{pid}/cancel").get_json()
    assert r["refund_amount"] == 100.0 and r["cancelled_by"] == "guest"
    assert db.one("SELECT status FROM payments WHERE booking_id = (SELECT id FROM bookings WHERE public_id = :p)",
                  {"p": pid})["status"] == "partially_refunded"


def test_review_requires_completed_stay_and_updates_rating(make_user, make_listing):
    host = make_user(roles=("host", "guest"))
    listing = make_listing(host.user_id)
    guest = make_user()
    pid = guest.post(f"/listings/{listing['public_id']}/bookings",
                     json={"check_in": d(60), "check_out": d(62), "guests": 1}).get_json()["public_id"]
    guest.post(f"/bookings/{pid}/pay")
    r = guest.post(f"/bookings/{pid}/review", json={"rating": 5, "comment": "Wonderful place to stay!"})
    assert r.status_code == 409  # trigger: stay not completed yet
    db.execute("UPDATE bookings SET status = 'completed' WHERE public_id = :p", {"p": pid})
    assert guest.post(f"/bookings/{pid}/review", json={"rating": 4, "comment": "Great stay, lovely host."}).status_code == 201
    assert guest.post(f"/bookings/{pid}/review", json={"rating": 1, "comment": "Trying to review twice"}).status_code == 409
    stats = db.one("SELECT review_count, rating_avg FROM listing_stats WHERE listing_id = :l", {"l": listing["id"]})
    assert stats == {"review_count": 1, "rating_avg": 4.0}


def test_search_by_dates_excludes_booked_listings(make_user, make_listing, client):
    host = make_user(roles=("host", "guest"))
    city = "Testville"
    free = make_listing(host.user_id, city=city)
    booked = make_listing(host.user_id, city=city)
    guest = make_user()
    pid = guest.post(f"/listings/{booked['public_id']}/bookings",
                     json={"check_in": d(30), "check_out": d(33), "guests": 1}).get_json()["public_id"]
    guest.post(f"/bookings/{pid}/pay")
    found = {i["public_id"] for i in client.get(f"/listings?city={city}&check_in={d(31)}&check_out={d(32)}").get_json()["items"]}
    assert found == {free["public_id"]}
    found = {i["public_id"] for i in client.get(f"/listings?city={city}&check_in={d(33)}&check_out={d(35)}").get_json()["items"]}
    assert found == {free["public_id"], booked["public_id"]}  # check-out day is free again
