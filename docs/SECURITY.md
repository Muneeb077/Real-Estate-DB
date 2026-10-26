# Security and encryption

## What changed from the original app

The coursework version stored and compared passwords in plaintext, and exposed a **public "Download Backup" button** that ran `mysqldump` as root, so anyone could download the database, passwords included. It also hard-coded the root DB password and Flask secret, never created a session for client logins, let any agent edit any property (IDOR), reset passwords with just a username and phone number, and had no CSRF protection or rate limiting. [PLAN.md](PLAN.md) has the full audit. Every item is fixed on this branch.

## Layers

| Layer | Implementation | Code |
|---|---|---|
| Passwords | Argon2id (19 MiB, t=2), rehash on login when parameters change, constant-time failure for unknown emails, strength rules | `app/security/passwords.py` |
| PII at rest | **Envelope encryption.** Each value gets a fresh 256-bit data key (AES-256-GCM); the data key is wrapped by a versioned key-encryption key. The column name is bound as GCM associated data, so ciphertext copied into another column fails to decrypt. Encrypted: email, phone, exact street address, host license, payout details, MFA secret, message bodies. | `app/security/crypto.py` |
| Lookups on encrypted data | **Blind indexes:** `HMAC-SHA256(key, context ‖ normalised value)` gives unique constraints and equality search (login by email, admin email search, duplicate phone) without the database ever seeing plaintext | `crypto.blind_index` |
| Key rotation | Add `v2` to `KEK_KEYS`, set `KEK_ACTIVE=v2`, run `scripts/rotate_keys.py`. Only the wrapped 48-byte data keys are rewritten, never the data. `--report` shows ciphertexts per key id; retire `v1` once it reaches zero | `app/keyrotation.py` |
| Sessions | 15-minute JWT access token and a 14-day opaque refresh token, both in `httpOnly` cookies (refresh scoped to `/api/v1/auth`, `SameSite=Strict`). Refresh tokens are stored as SHA-256 hashes, rotate on every use, and **reusing a rotated token revokes the whole token family**. Users can list and revoke sessions | `app/security/tokens.py` |
| CSRF | Double-submit token: a readable cookie whose value must be echoed in `X-CSRF-Token` on every unsafe request (Stripe webhook exempt, it's signature-verified) | `app/security/rbac.py` |
| MFA | TOTP with ±1 step drift; the last used step is stored, so a code can't be replayed. 8 recovery codes stored as hashes. **Required for the admin console**: admin routes need the admin role *and* an access token minted after a TOTP check | `app/security/mfa.py`, `rbac.roles_required` |
| Account protection | Lockout after 5 failures in 15 minutes (tracked by email blind index, so it works for non-existent accounts too); per-route rate limits; enumeration-safe password reset with 32-byte single-use tokens (hashed, 30-minute expiry) that sign out every device | `app/api/auth.py` |
| Authorisation | Role decorators; every host and guest write checks ownership in its SQL `WHERE` (tested: one host gets 404 on another's listing); `extra="forbid"` request models block mass assignment (`{"role": "admin"}` is a 422) | `app/api/*` |
| Data minimisation | Public API reads only `v_public_listings` (no private columns, coordinates rounded to ~100 m). Exact address and phone are decrypted only for the two parties to a confirmed booking. Admin PII views are written to the audit log | `listings.py`, `stays.py`, `admin.py` |
| Uploads | Pillow decodes and re-encodes every image to WebP, which validates it, strips all EXIF (GPS, camera serials) and normalises orientation. Format allowlist, size and pixel limits (decompression-bomb guard) | `app/storage.py` |
| Transit | Nginx TLS 1.2/1.3, HSTS, CSP, frame denial, plus security headers from Next.js. MySQL has `require_secure_transport=ON`, all accounts `REQUIRE SSL`, and the app, migrations and mysqldump connect with TLS | `docker/nginx`, `docker/mysql`, `app/db.py` |
| Database at rest | InnoDB TDE via the keyring component: per-tablespace keys, encrypted redo, undo and binlogs, master key rotation | `db/security/enable_tde.sql` |
| Backups | Admin-only. `mysqldump` runs as a read-only account with its password in `MYSQL_PWD` (not in argv) and **streams through chunked AES-256-GCM**, so plaintext never touches disk. Chunk index and a last-chunk flag are bound as associated data, so reordered, dropped or truncated chunks fail to decrypt. SHA-256 is recorded, downloads are audited, and restore uses `scripts/decrypt_backup.py` | `app/backups.py` |
| Audit | Triggers record who changed what (`@actor_id`). The log is append-only (UPDATE and DELETE are rejected by triggers) and partitioned by year | `db/schema/0005_admin.sql` |
| Errors and secrets | All config comes from the environment; the app refuses to start without its secrets. Errors are generic JSON; internals are only logged. `debug` is off | `app/config.py`, `app/errors.py` |
| Supply chain | `pip-audit`, `npm audit` and Dependabot in CI | `.github/` |

## How it was verified

These were run during development; the tests are in `backend/tests/`.

- **Ciphertext at rest:** tests read the raw columns and assert that the plaintext isn't present, then decrypt through the app (`test_signup_stores_only_hashes_and_ciphertext`, `test_messages_are_encrypted_at_rest`, `test_phone_is_encrypted_with_blind_index`).
- **Context binding and tamper resistance:** `test_round_trip_and_context_binding`, `test_encrypted_backup_round_trip` (flipping one byte raises `InvalidTag`).
- **Key rotation:** `test_kek_rotation_rewraps_everything` rotates to `v2`, then decrypts with a keyring that contains *only* `v2`.
- **TLS:** with `require_secure_transport=ON`, the API's session reports `Ssl_version = TLSv1.3` (`TLS_AES_128_GCM_SHA256`), and `mysql --ssl-mode=DISABLED` is refused with error 3159.
- **TDE:** on a MySQL instance with `component_keyring_file`, `enable_tde.sql` encrypted all 45 tablespaces and `binlog_encryption=ON`. A canary string written to an unencrypted control table appears in its `.ibd` file; the same string in encrypted tables does not. On a server *without* a keyring, the script aborts before changing anything.
- **Sessions:** `test_refresh_rotation_and_reuse_detection`, `test_password_reset_token_is_single_use`, `test_mfa_enrolment_and_login` (the enrolment code is rejected on replay), `test_admin_needs_mfa`.

## Known limits

- The keyring is `LocalKeyring` (KEKs from environment variables). In production the KEK should live in a KMS or HSM (AWS KMS, GCP KMS, Vault Transit), with `wrap` and `unwrap` as API calls; the interface is already isolated for that. MySQL TDE should likewise use a KMS-backed keyring or the cloud provider's storage encryption.
- Messages are encrypted at rest on the server, not end-to-end: the server can decrypt them (it must, to show them in the inbox and export them).
- Search filters on city and price, so those columns are not encrypted; only identifying details are.
- Rate limits are counted per API process without Redis; set `REDIS_URL` when running several instances. (Account lockout is stored in MySQL, so it is already shared.)
