"""
Seeds the database with demo accounts and turns the legacy CSVs
(Dummy_Agent_Data.csv, Dummy_Property_Data_with_Agent_IDs.csv) into realistic
marketplace listings: titles, descriptions, cities with coordinates, photos,
amenities. Legacy ids are kept in host_profiles.legacy_agent_id and
listings.legacy_p_id. Legacy plaintext passwords are NOT carried over.

    python scripts/seed.py            # all 50,000 listings
    python scripts/seed.py --limit 2000
"""
import argparse
import csv
import json
import os
import random
import sys
import time
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ulid import ULID

from app import create_app, db
from app.security import crypto, mfa
from app.security.passwords import hash_password

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEMO_PASSWORD = "HomeNest-demo-2026"
BATCH = 2000

CITIES = [
    ("New York", "NY", "US", 40.7128, -74.0060, 1.6), ("Los Angeles", "CA", "US", 34.0522, -118.2437, 1.4),
    ("Chicago", "IL", "US", 41.8781, -87.6298, 0.9), ("Miami", "FL", "US", 25.7617, -80.1918, 1.2),
    ("Austin", "TX", "US", 30.2672, -97.7431, 1.0), ("Seattle", "WA", "US", 47.6062, -122.3321, 1.3),
    ("San Francisco", "CA", "US", 37.7749, -122.4194, 1.8), ("Boston", "MA", "US", 42.3601, -71.0589, 1.4),
    ("Denver", "CO", "US", 39.7392, -104.9903, 1.0), ("Nashville", "TN", "US", 36.1627, -86.7816, 0.9),
    ("San Diego", "CA", "US", 32.7157, -117.1611, 1.4), ("Portland", "OR", "US", 45.5152, -122.6784, 1.0),
    ("Atlanta", "GA", "US", 33.7490, -84.3880, 0.9), ("Phoenix", "AZ", "US", 33.4484, -112.0740, 0.8),
    ("New Orleans", "LA", "US", 29.9511, -90.0715, 0.8), ("Honolulu", "HI", "US", 21.3069, -157.8583, 1.6),
    ("Toronto", "ON", "CA", 43.6532, -79.3832, 1.2), ("Vancouver", "BC", "CA", 49.2827, -123.1207, 1.4),
    ("London", None, "GB", 51.5074, -0.1278, 1.7), ("Paris", None, "FR", 48.8566, 2.3522, 1.6),
    ("Barcelona", None, "ES", 41.3874, 2.1686, 1.1), ("Lisbon", None, "PT", 38.7223, -9.1393, 0.9),
    ("Amsterdam", None, "NL", 52.3676, 4.9041, 1.4), ("Berlin", None, "DE", 52.5200, 13.4050, 1.0),
    ("Rome", None, "IT", 41.9028, 12.4964, 1.1), ("Dubai", None, "AE", 25.2048, 55.2708, 1.5),
    ("Tokyo", None, "JP", 35.6762, 139.6503, 1.3), ("Sydney", "NSW", "AU", -33.8688, 151.2093, 1.4),
    ("Lahore", "PB", "PK", 31.5204, 74.3587, 0.4), ("Islamabad", "IS", "PK", 33.6844, 73.0479, 0.45),
    ("Karachi", "SD", "PK", 24.8607, 67.0011, 0.4), ("Mexico City", None, "MX", 19.4326, -99.1332, 0.6),
    ("Cape Town", None, "ZA", -33.9249, 18.4241, 0.7), ("Bali", None, "ID", -8.4095, 115.1889, 0.6),
]

STREETS = ["Maple", "Oak", "Cedar", "Pine", "Elm", "Willow", "Lake", "Hill", "Sunset", "Park", "River",
           "Harbor", "Garden", "Highland", "Meadow", "Bay", "Ocean", "Forest", "Valley", "Spring"]
SUFFIX = ["St", "Ave", "Rd", "Blvd", "Lane", "Way", "Drive", "Court"]
ADJ = ["Sunny", "Modern", "Cozy", "Spacious", "Bright", "Charming", "Elegant", "Quiet", "Stylish", "Light-filled",
       "Renovated", "Airy", "Classic", "Minimalist", "Luxury", "Rustic", "Contemporary", "Peaceful"]
FEATURE = ["with city views", "near the park", "with private garden", "steps from the beach", "with rooftop terrace",
           "in the historic district", "with open-plan kitchen", "close to transit", "with mountain views",
           "by the waterfront", "with home office", "with balcony", "in a leafy neighbourhood"]
TYPES = {"house": 0.24, "apartment": 0.30, "condo": 0.14, "townhouse": 0.10, "villa": 0.06,
         "cabin": 0.05, "studio": 0.07, "loft": 0.04}
DESC = [
    "Natural light pours through large windows into an open living space with high ceilings.",
    "The kitchen was renovated recently and has stone counters, a gas range and plenty of storage.",
    "Bedrooms are set away from the living area for privacy, each with built-in wardrobes.",
    "A short walk brings you to cafes, grocery stores and public transport.",
    "Outdoor space is ideal for morning coffee or dinner with friends.",
    "The building is well maintained with secure entry and on-site management.",
    "Hardwood floors run throughout, and the bathrooms have been updated with modern fixtures.",
    "Families will appreciate the nearby schools, playgrounds and quiet streets.",
    "Fast fibre internet and a dedicated desk make remote work easy.",
    "Energy-efficient appliances and double glazing keep running costs low.",
]


def weighted_type():
    return random.choices(list(TYPES), weights=list(TYPES.values()))[0]


def make_listing(row, host_id, address_id, idx):
    """
    Converts one legacy Property row into a marketplace listing.
    """
    legacy_price = float(row["p_price"])
    sqft = max(350, int(row["p_size"]))
    city = CITIES[idx % len(CITIES)]
    factor = city[5]
    ptype = weighted_type()
    beds = 0 if ptype == "studio" else max(1, min(7, round(sqft / 650 + random.uniform(-0.6, 0.6))))
    baths = max(1.0, min(5.0, round((beds * 0.7 + random.choice([0, 0.5, 1])) * 2) / 2))

    if row["p_type"] == "sale":
        mode, unit = "sale", "total"
        price = round(legacy_price * factor * random.uniform(0.9, 1.6), -3)
        status = "sold" if row["p_status"] == "sold" else "published"
        guests = None
    else:
        # The legacy schema had one "rent" type: split it into the two rental modes.
        if random.random() < 0.55:
            mode, unit = "short_term_stay", "night"
            price = round(max(45, min(1200, (legacy_price / 4500) * factor * random.uniform(0.6, 1.3))))
            guests = max(1, min(16, beds * 2 + random.choice([0, 0, 1, 2])))
        else:
            mode, unit = "long_term_rent", "month"
            price = round(max(700, min(25000, (legacy_price / 180) * factor * random.uniform(0.6, 1.2))), -1)
            guests = None
        status = "rented" if row["p_status"] == "sold" and mode == "long_term_rent" else "published"

    title = f"{random.choice(ADJ)} {beds or 'studio'}{' bed' if beds else ''} {ptype} {random.choice(FEATURE)}"
    title = title.replace("studio studio", "studio")
    description = " ".join(random.sample(DESC, k=random.randint(3, 5)))
    published = date.today() - timedelta(days=random.randint(1, 700))
    return dict(
        public_id=str(ULID()), host_id=host_id, address_id=address_id, title=title[:140].capitalize(),
        description=description, listing_mode=mode, property_type=ptype, bedrooms=beds, bathrooms=baths,
        max_guests=guests, size_sqft=sqft, price=price, price_unit=unit, status=status,
        legacy_p_id=int(row["p_id"]), published_at=published.isoformat(),
    )


def next_id(cur, table):
    # The seed runs alone, so a batch's AUTO_INCREMENT ids are consecutive from MAX(id)+1.
    cur.execute(f"SELECT COALESCE(MAX(id), 0) + 1 FROM {table}")
    return cur.fetchone()[0]


def check_ids(cur, table, first, n):
    cur.execute(f"SELECT MIN(id), MAX(id) FROM {table} WHERE id >= %s", (first,))
    lo, hi = cur.fetchone()
    if (lo, hi) != (first, first + n - 1):
        raise RuntimeError(f"Unexpected id range in {table}: {lo}..{hi}, expected {first}..{first + n - 1}")


def create_user(conn, email, name, roles, verified=True, mfa_secret=None):
    pid = str(ULID())
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO users (public_id, email_enc, email_hash, email_verified_at, password_hash,
                              mfa_secret_enc, mfa_enabled_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (pid, crypto.encrypt(email, "users.email"), crypto.blind_index(email, "users.email"),
         "2026-01-01" if verified else None, hash_password(DEMO_PASSWORD),
         crypto.encrypt(mfa_secret, "users.mfa_secret") if mfa_secret else None,
         "2026-01-01" if mfa_secret else None),
    )
    uid = cur.lastrowid
    cur.executemany("INSERT INTO user_roles (user_id, role) VALUES (%s, %s)", [(uid, r) for r in roles])
    cur.execute("INSERT INTO user_profiles (user_id, display_name, avatar_url) VALUES (%s, %s, %s)",
                (uid, name, f"https://i.pravatar.cc/150?u={pid}"))
    return uid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    random.seed(42)
    started = time.time()

    app = create_app()
    with app.app_context():
        raw = db.engine().raw_connection()
        conn = raw.driver_connection
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0]:
            sys.exit("Database already has users; seed only an empty database.")

        admin_secret = mfa.new_secret()
        create_user(conn, "admin@homenest.dev", "Avery Admin", ["admin", "guest"], mfa_secret=admin_secret)
        create_user(conn, "guest@homenest.dev", "Gina Guest", ["guest"])
        guests = [create_user(conn, f"guest{i}@homenest.dev", f"Guest {i}", ["guest"]) for i in range(1, 21)]

        # Legacy agents become verified hosts.
        hosts = {}
        with open(os.path.join(ROOT, "Dummy_Agent_Data.csv")) as f:
            for i, r in enumerate(csv.DictReader(f)):
                email = "host@homenest.dev" if i == 0 else f"agent{r['agent_id']}@homenest.dev"
                uid = create_user(conn, email, r["agent_name"], ["host", "guest"])
                cur.execute(
                    """INSERT INTO host_profiles (user_id, agency_name, license_enc, verification_status,
                                                  verified_at, legacy_agent_id)
                       VALUES (%s, %s, %s, 'verified', NOW(), %s)""",
                    (uid, f"{r['agent_name']} Realty", crypto.encrypt(f"LIC-{r['agent_id']}", "host_profiles.license"),
                     int(r["agent_id"])))
                cur.execute("UPDATE user_profiles SET phone_enc = %s, phone_hash = %s WHERE user_id = %s",
                            (crypto.encrypt(r["agent_contact"], "user_profiles.phone"),
                             crypto.blind_index(r["agent_contact"], "user_profiles.phone"), uid))
                hosts[int(r["agent_id"])] = uid
        conn.commit()

        cur.execute("SELECT id, code FROM amenities")
        amenity_ids = [r[0] for r in cur.fetchall()]

        with open(os.path.join(ROOT, "Dummy_Property_Data_with_Agent_IDs.csv")) as f:
            rows = list(csv.DictReader(f))
        if args.limit:
            rows = rows[: args.limit]

        total = 0
        for start in range(0, len(rows), BATCH):
            chunk = rows[start:start + BATCH]
            # addresses: insert the batch, then read back the ids (AUTO_INCREMENT is consecutive in one statement)
            addr_values = []
            for i, _ in enumerate(chunk):
                c = CITIES[(start + i) % len(CITIES)]
                lat = c[3] + random.uniform(-0.08, 0.08)
                lng = c[4] + random.uniform(-0.1, 0.1)
                street = f"{random.randint(1, 9999)} {random.choice(STREETS)} {random.choice(SUFFIX)}"
                addr_values.append((crypto.encrypt(street, "addresses.street"), c[0], c[1],
                                    f"{random.randint(10000, 99999)}", c[2], f"POINT({lat:.6f} {lng:.6f})"))
            first_addr = next_id(cur, "addresses")
            cur.executemany(
                """INSERT INTO addresses (street_enc, city, state, postal_code, country, location)
                   VALUES (%s, %s, %s, %s, %s, ST_GeomFromText(%s, 4326))""", addr_values)

            listings = [make_listing(r, hosts[int(r["agent_id"])], first_addr + i, start + i)
                        for i, r in enumerate(chunk)]
            first_listing = next_id(cur, "listings")
            cols = list(listings[0])
            cur.executemany(
                f"INSERT INTO listings ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
                [tuple(l[c] for c in cols) for l in listings])
            check_ids(cur, "listings", first_listing, len(chunk))

            photos, amen = [], []
            for i in range(len(chunk)):
                lid = first_listing + i
                for n in range(random.randint(4, 6)):
                    seed = f"hn{lid}x{n}"
                    photos.append((lid, f"https://picsum.photos/seed/{seed}/1200/800",
                                   f"https://picsum.photos/seed/{seed}/480/320", f"Photo {n + 1}", n))
                for a in random.sample(amenity_ids, k=random.randint(5, 12)):
                    amen.append((lid, a))
            cur.executemany("INSERT INTO listing_photos (listing_id, url, thumb_url, alt, sort_order) "
                            "VALUES (%s, %s, %s, %s, %s)", photos)
            cur.executemany("INSERT INTO listing_amenities (listing_id, amenity_id) VALUES (%s, %s)", amen)
            conn.commit()
            total += len(chunk)
            print(f"  {total:>6} listings", file=sys.stderr)

        # A few views/favourites so dashboards have data before real traffic arrives.
        cur.execute("UPDATE listing_stats SET views = FLOOR(RAND(7) * 400), favorites = FLOOR(RAND(9) * 25)")
        conn.commit()
        raw.close()

    print(json.dumps({
        "listings": total,
        "seconds": round(time.time() - started, 1),
        "password_for_all_demo_accounts": DEMO_PASSWORD,
        "accounts": ["admin@homenest.dev (admin, MFA on)", "host@homenest.dev (host)", "guest@homenest.dev (guest)"],
        "admin_totp_secret": admin_secret,
        "admin_totp_uri": mfa.provisioning_uri(admin_secret, "admin@homenest.dev"),
    }, indent=2))


if __name__ == "__main__":
    main()
