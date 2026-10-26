"""
KEK rotation. Every encrypted column stores its data key wrapped under some KEK
id; rotation re-wraps those 48-byte keys under the active KEK. Data ciphertext is
untouched, so rotating 50k rows takes seconds, and the old KEK can be retired
once nothing references it.
"""
from . import db
from .security.crypto import cipher

# (table, primary key, column, AAD context) for every envelope-encrypted column
ENCRYPTED_COLUMNS = [
    ("users", "id", "email_enc", "users.email"),
    ("user_profiles", "user_id", "phone_enc", "user_profiles.phone"),
    ("host_profiles", "user_id", "license_enc", "host_profiles.license"),
    ("host_profiles", "user_id", "payout_enc", "host_profiles.payout"),
    ("addresses", "id", "street_enc", "addresses.street"),
    ("messages", "id", "body_enc", "messages.body"),
]


def key_usage():
    """
    Count of ciphertexts per KEK id, per column (reads the KEK id from each blob header).
    """
    usage = {}
    for table, pk, col, _ in ENCRYPTED_COLUMNS:
        rows = db.query(
            f"""SELECT CAST(SUBSTRING({col}, 3, ORD(SUBSTRING({col}, 2, 1))) AS CHAR) AS kid, COUNT(*) AS n
                FROM {table} WHERE {col} IS NOT NULL GROUP BY kid""")
        usage[f"{table}.{col}"] = {r["kid"]: r["n"] for r in rows}
    return usage


def rotate(batch=1000, log=print):
    c = cipher()
    active = c.keyring.active_id()
    total = 0
    for table, pk, col, context in ENCRYPTED_COLUMNS:
        last = 0
        while True:
            rows = db.query(
                f"""SELECT {pk} AS pk, {col} AS ciphertext FROM {table}
                    WHERE {col} IS NOT NULL AND {pk} > :last
                      AND CAST(SUBSTRING({col}, 3, ORD(SUBSTRING({col}, 2, 1))) AS CHAR) <> :active
                    ORDER BY {pk} LIMIT :n""", {"last": last, "active": active, "n": batch})
            if not rows:
                break
            with db.transaction() as conn:
                for r in rows:
                    db.execute(f"UPDATE {table} SET {col} = :b WHERE {pk} = :pk",
                               {"b": c.rewrap(r["ciphertext"], context), "pk": r["pk"]}, conn=conn)
            total += len(rows)
            last = rows[-1]["pk"]
            log(f"  {table}.{col}: re-wrapped {len(rows)} (up to {pk}={last})")
    return total
