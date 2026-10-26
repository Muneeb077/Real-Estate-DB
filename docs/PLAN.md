# Real Estate → Public Listings Marketplace (DB + Encryption + Modern Frontend)

## Context
The project (Flask + MySQL, `real_estate_codebase/`, schema in `real_estate.sql`) was built to show database skills: stored procedures (`GetProperties`, `FilterProperties`), functions (`GetMaxAgentId`, `GetMaxPropertyId`), and a trigger (`after_property_sold`). The goal now is a portfolio piece that also shows **security/encryption** and a **modern frontend**, and that works like Airbnb: **anyone can browse listings without an account**, and accounts are only needed to act (save, inquire, book, list, moderate). It must support many concurrent users with three roles: **guest/client, host/agent, admin**.

Defaults chosen (questions were declined, change any of these if you prefer otherwise):
- **Backend:** Flask kept, but rebuilt as a JSON REST API (app factory + blueprints + SQLAlchemy Core/ORM on top of your SQL objects).
- **Frontend:** Next.js (React, TypeScript) + Tailwind + shadcn/ui, with a map view (Leaflet/MapLibre).
- **Database:** stay on **MySQL 8** so your procedures/triggers carry over. MySQL 8 adds CTEs, window functions, spatial indexes, FULLTEXT, CHECK constraints and JSON.
- **Listing modes:** `sale`, `long_term_rent`, `short_term_stay` (the Airbnb part, with nightly pricing and bookings).

---

## 1. Audit of the current code (what is broken or insecure)

### Critical security issues
| # | Issue | Where |
|---|---|---|
| S1 | **Passwords stored and compared in plaintext** (`c_password`, `agent_password`; `==` comparison). Seed CSV also has plaintext passwords. | `client.py`, `agent.py`, `app.py:login/agent_login`, `Dummy_Agent_Data.csv` |
| S2 | **Public "Download Backup" button** runs `mysqldump` as root and gives the whole database, plaintext passwords included, to anyone, no login required. | `app.py:/backup`, `main_page.html` |
| S3 | **Hard-coded root DB credentials** (`root` / `root1234`) in two places; app connects as root. | `dbconnection.py`, `app.py:/backup` |
| S4 | **Hard-coded Flask secret key** `"your_secret_key"`, so anyone can forge session cookies and log in as any agent. | `app.py:8` |
| S5 | **Client login never creates a session**, and `/client_mainpage` has no auth check. "Login" is cosmetic. | `app.py:login`, `client_main_page` |
| S6 | **Password reset with nothing more than username + phone number**: anyone who knows a phone number can take over the account. No token, no email, no rate limit. | `forgotpassword`, `agent_forgotpassword` |
| S7 | **IDOR:** `modify_property` doesn't check that the property belongs to the logged-in agent, so any agent can edit any listing. | `property.py:modify_property` |
| S8 | No CSRF protection on any POST form; `debug=True` in production; raw exception text flashed to users. | `app.py` |
| S9 | Agent IDs are sequential and shown before signup, which makes enumeration easy (and they double as the login username). | `agent_signup` |
| S10 | No rate limiting or lockout on login, so brute force is easy. | all login routes |

### Correctness / database bugs
- **`sell_property` always fails:** `Transactions.t_id` is `NOT NULL` without `AUTO_INCREMENT`, but the code inserts `NULL`.
- **Sale isn't atomic:** the property is committed as `sold` before the transaction row is inserted. If the insert fails, the property is sold with no transaction. Commission is also calculated in Python and again in the trigger (`TransactionLog`), with different types (INT vs DECIMAL).
- **ID generation via `MAX()+1`** (`GetMaxAgentId`, `GetMaxPropertyId`) is a race condition when two users sign up at the same moment. `Agent.agent_id` is already `AUTO_INCREMENT` but the code ignores it.
- **Wrong Agent ID shown after signup:** `agent.get_agent_id()` returns the *previous* max ID from the global instance, not the new one.
- **Forgot password reversed logic:** routes call `forgot_password` and redirect even when contact doesn't match. The user gets no feedback, and it fails silently.
- `GetProperties` requires *both* min and max or ignores the filter; `p_price INT` for money; `Transactions.t_date DATE` loses time; typo `commision`.
- Global singletons `Client()/Agent()/Property()` with shared `self.db.connection` are **not thread-safe**: concurrent requests overwrite each other's connection. Every call opens a new connection (no pool).
- Client table lists "No properties" with `colspan=5` but has 6 columns; property type filter is free text against an ENUM.
- `transaction.py` (`update_transaction_table`) is dead code.

### Missing for a marketplace
Properties have no title, description, address, coordinates, bedrooms/bathrooms, photos, amenities, or timestamps, so there is nothing to show on an Airbnb-style card. No admin role exists. No pagination: the 50k-row CSV would render as one HTML table.

---

## 2. Target architecture

```
Next.js (SSR/ISR for public listing pages, SEO)  ──HTTPS──▶  Flask API (/api/v1, JWT in httpOnly cookies)
                                                               │  SQLAlchemy pool, Alembic migrations
                                                               ├─▶ MySQL 8 (primary)  ─▶ read replica (later)
                                                               ├─▶ Redis (sessions/rate limits/cache/queues)
                                                               ├─▶ S3/MinIO (listing photos, KYC docs, encrypted)
                                                               └─▶ Celery/RQ worker (emails, image resize, backups)
Docker Compose for all services; Nginx reverse proxy with TLS.
```

Backend restructure (`real_estate_codebase/` → `backend/app/`):
- `app/__init__.py` app factory; config from env vars (`.env`, never committed), `python-dotenv`.
- Blueprints: `auth`, `listings`, `bookings`, `inquiries`, `reviews`, `users`, `admin`, `media`.
- `app/db.py`: SQLAlchemy engine with a connection pool, replacing `dbconnection.py`. Keep calling your procedures via `session.execute(text("CALL ..."))` so the SQL work stays visible.
- Validation with Pydantic/Marshmallow. Uniform JSON error format. Never return raw exceptions.
- Migrations: Alembic. Convert `real_estate.sql` into the baseline migration; keep a `/db` folder with procedures, triggers, views and seed scripts as standalone `.sql` files, which shows them off in the repo.

---

## 3. Database redesign (the showcase)

### Core tables (normalized, InnoDB, utf8mb4)
- **users**: `id BIGINT AUTO_INCREMENT`, `public_id CHAR(26)` (ULID, exposed in URLs instead of sequential IDs), `email` (unique), `email_verified_at`, `password_hash`, `role ENUM('guest','host','admin')` *or* `user_roles` join table (better: supports a user who is both guest and host), `status ENUM('active','suspended','deleted')`, `mfa_secret_enc`, `created_at`, `updated_at`, `deleted_at` (soft delete).
- **user_profiles**: name, avatar, bio, `phone_enc`, `phone_hash` (for lookup), languages.
- **host_profiles** (replaces `Agent`): license number (encrypted), agency, verification status, payout details (encrypted), commission rate.
- **addresses**: street/city/state/postal/country, `location POINT SRID 4326` + `SPATIAL INDEX`.
- **listings** (replaces `Property`): `public_id`, `host_id`, `title`, `description`, `listing_mode ENUM('sale','long_term_rent','short_term_stay')`, `property_type` (house/apartment/condo/villa…), `bedrooms`, `bathrooms`, `max_guests`, `size_sqft`, `price DECIMAL(12,2)`, `currency CHAR(3)`, `price_unit ENUM('total','month','night')`, `status ENUM('draft','pending_review','published','paused','sold','rented','archived')`, `address_id`, timestamps, `FULLTEXT(title, description)`, `CHECK (price > 0)`.
- **listing_photos** (url, order, alt), **amenities** + **listing_amenities** (M:N).
- **availability** / **blocked_dates** per listing; **price_rules** (weekend/seasonal pricing).
- **bookings** (short-term): guest, listing, `check_in`, `check_out`, guests, `total_price`, `status ENUM('pending','confirmed','cancelled','completed')`. **Overlap prevention** with a `BEFORE INSERT` trigger + `SELECT … FOR UPDATE` inside a procedure `CreateBooking()`.
- **inquiries / messages** (guest↔host conversation threads), **viewings** (sale/rent appointment slots).
- **offers** (sale): amount, status. Accepting one calls `CompleteSale()`.
- **transactions** (fixed): `AUTO_INCREMENT`, `DECIMAL` amounts, `DATETIME`, links to booking *or* offer, commission computed in **one** place (the procedure).
- **payments** (Stripe test mode): stores only Stripe IDs, never card data.
- **reviews**: one per completed booking (enforced by a UNIQUE key on `booking_id`), rating CHECK 1–5, host reply.
- **favorites** (wishlists), **saved_searches**, **notifications**.
- **audit_log**: `actor_id, action, entity, entity_id, old_json, new_json, ip, ts`, filled by triggers on sensitive tables.
- **refresh_tokens / sessions**, **password_reset_tokens** (stores *hash* of token + expiry), **login_attempts**.

### DB features to showcase
- **Stored procedures (transactions + locking):** `CreateBooking`, `CancelBooking` (refund policy), `CompleteSale` (replaces `sell_property`: one `START TRANSACTION … COMMIT` with a `SIGNAL` on error), `SearchListings` (dynamic filters, keyset pagination).
- **Triggers:** booking overlap guard, audit logging, `listings.updated_at`, auto-update `listing_stats.avg_rating` after a review insert.
- **Views:** `v_public_listings` (only published listings, no private columns; the public API reads only this), `v_host_dashboard`, `v_admin_kpis`.
- **Window functions / CTEs** for analytics: monthly revenue per host, occupancy rate, price percentile per city, top hosts ranking (`RANK() OVER`).
- **Spatial queries:** "listings within X km" (`ST_Distance_Sphere`) and map bounding box (`MBRContains`).
- **Full-text search** on title/description (`MATCH … AGAINST` in boolean mode).
- **Indexing strategy:** composite indexes `(status, listing_mode, city, price)`, covering index for cards; show `EXPLAIN ANALYZE` before/after in the README.
- **Least-privilege DB users:** `app_rw` (DML only on app tables, `EXECUTE` on procedures), `app_ro` (reads for replicas/analytics), `backup_user`, `migrator` (DDL). The app never uses root.
- **Events** (`CREATE EVENT`): expire pending bookings after 30 min, purge expired reset tokens, nightly stats rollup.
- **Seed data:** convert the 50k CSV into realistic listings (Faker: titles, cities with coordinates, photos from Unsplash URLs) to demonstrate pagination and index performance at scale.

---

## 4. Encryption & security (what's missing → what to add)

| Layer | Missing today | Add |
|---|---|---|
| **Passwords** | Plaintext | **Argon2id** (`argon2-cffi`) with per-user salt; rehash on login if parameters change. Migration: hash existing rows once with a script. |
| **Data in transit** | HTTP only; MySQL connection unencrypted | HTTPS via Nginx + Let's Encrypt (mkcert locally), HSTS; **MySQL `require_secure_transport=ON`** with TLS certs; Redis TLS in prod. |
| **PII at rest (app-level field encryption)** | Phone, address stored plain | **AES-256-GCM envelope encryption** (`cryptography`): per-record data key encrypted by a master key (KEK) from env/KMS (AWS KMS or HashiCorp Vault for the demo). Encrypt `phone`, license numbers, payout info, MFA secret, exact street address (show only approximate location publicly, like Airbnb). Store `key_version` to support **key rotation**. |
| **Searchable encrypted fields** | n/a | **Blind index**: `HMAC-SHA256(pepper, normalized_email/phone)` column for unique lookups without decrypting. |
| **Database at rest** | None | **InnoDB tablespace encryption** (`keyring_file` component, `ENCRYPTION='Y'` on tables), and encrypted binlogs/redo logs. |
| **Backups** | Public, plaintext dump of all data | Admin-only, async job: `mysqldump --single-transaction` as `backup_user`, then **age/GPG or AES-GCM encrypted**, uploaded to S3 with SSE-KMS; record checksum + download audit. Remove the button from the public page. |
| **Sessions/auth tokens** | Forgeable cookie (hard-coded key) | Secret from env; **short-lived JWT access token (15 min) + rotating refresh token** in `httpOnly; Secure; SameSite=Lax` cookies, refresh tokens stored *hashed* and revocable; CSRF double-submit token. |
| **Password reset** | Username + phone only | Email link with random 32-byte token, store **SHA-256 hash**, 30-min expiry, single use; responses identical whether the account exists or not. |
| **MFA** | None | TOTP (`pyotp`) for hosts/admins (required for admins); recovery codes stored hashed. |
| **Uploads** | n/a | Signed (pre-signed) S3 URLs, MIME/size validation, EXIF stripping; KYC/ID documents encrypted with SSE-KMS and private. |
| **Messages** | n/a | Optional showcase: guest↔host messages encrypted at rest with AES-GCM (server-side), or E2E with libsodium in the browser as a stretch goal. |
| **Secrets** | Committed in code | `.env` + `.env.example`, `.gitignore`; rotate the `root1234` password (it's in git history). |
| **Other hardening** | — | Rate limiting (`Flask-Limiter` + Redis) and account lockout; security headers (CSP, X-Frame-Options) via `flask-talisman`; RBAC decorators; ownership checks on every write (fixes S7); input validation; `debug=False`; dependency scanning (`pip-audit`, `npm audit`, Dependabot); audit log of admin actions. |

---

## 5. Roles & multi-user features

**Public visitor (no account):** home page with search bar, browse/search listings, map view, listing detail page (photos, amenities, approximate location, host card, reviews, availability calendar), host public profile. This replaces "must sign up to see the DB": public pages read from `v_public_listings`.

**Guest / client (account):** sign up/in (email + Google OAuth optional), email verification; wishlists; saved searches with email alerts; send inquiries/messages; request viewings (sale/rent); make offers (sale); book short-term stays with Stripe test checkout; trips page; leave reviews after stay; profile & security settings (MFA, sessions list, change password, delete account, data export (GDPR-style)).

**Host / agent:** onboarding + verification (license upload); create/edit listings with multi-step form, photo upload/reorder, amenities, pricing rules, availability calendar; drafts → submit for review; inbox; manage bookings/viewings/offers (accept/decline); dashboard with earnings, occupancy, views→inquiries conversion (charts from your window-function queries); co-host/team support (agency with multiple agents) as a stretch goal.

**Admin:** dashboard KPIs (users, listings, bookings, revenue, by city/time); user management (suspend, role change, impersonate-read-only); listing moderation queue (approve/reject with reason); review/report moderation; host verification approvals; audit log viewer; encrypted backup trigger/download; feature flags/commission settings. Admin actions require MFA and are audited.

**Cross-cutting:** notifications (in-app + email via queue), reports/flags on listings and users, i18n/currency formatting, soft deletes.

---

## 6. Modern frontend (Next.js)
- **Pages:** `/` (hero search: location, dates, guests, mode tabs Buy / Rent / Stays), `/search` (filters drawer: price slider, beds/baths, type, amenities; grid of cards + **map split view** with price pins, "search as I move the map"), `/listings/[publicId]` (gallery, booking widget with date-range picker and live price breakdown, or "Request viewing / Make offer" for sale), `/wishlists`, `/trips`, `/inbox`, `/host/*` (dashboard, listings, calendar, earnings), `/admin/*`, `/account/*` (security, MFA setup with QR).
- **Tech:** TypeScript, Tailwind + shadcn/ui, TanStack Query for data, React Hook Form + Zod, Recharts for dashboards, MapLibre/Leaflet, `next/image`, dark mode, skeleton loaders, infinite scroll (keyset pagination from the API), responsive/mobile-first, accessibility (keyboard, ARIA).
- **SEO/performance:** SSR/ISR for listing pages, OpenGraph tags, sitemap.
- Optional realtime: Socket.IO/SSE for messages and booking status.

---

## 7. Scaling for many users
- Remove global singletons → per-request DB sessions with a **connection pool**; run with **Gunicorn** (multiple workers) behind Nginx.
- **Stateless API** (JWT + Redis), so multiple API containers can run behind the load balancer.
- **Redis cache** for hot searches/listing detail (invalidate on update); rate limiting.
- **Keyset pagination** everywhere; covering indexes; `EXPLAIN` checks.
- **Read replica** for search/analytics (`app_ro`), primary for writes. Mention sharding/partitioning: `PARTITION BY RANGE (YEAR(created_at))` on `bookings`/`audit_log`.
- **Concurrency correctness:** row locks in `CreateBooking`, optimistic locking (`version` column) on listing edits, idempotency keys on payment/booking endpoints.
- Background workers for email, image thumbnails (Pillow → WebP), backups, search alerts.
- Observability: structured logging, Sentry, health checks, Prometheus metrics. Load test with **Locust/k6** and publish results in the README.
- Deployment: Docker Compose locally; Render/Railway/Fly.io or AWS (ECS + RDS MySQL + S3 + ElastiCache) for a live demo; GitHub Actions CI (lint, tests, migrations, build).

---

## 8. Phased roadmap
1. **Phase 0, fix & secure (1 week):** move secrets to env, remove public backup, Argon2 hashing + migration script, real sessions for clients, ownership checks, CSRF, fix `Transactions` AUTO_INCREMENT + atomic `CompleteSale`, use `AUTO_INCREMENT` instead of `MAX()+1`, least-privilege DB user, `debug=False`.
2. **Phase 1, foundation:** repo split `backend/`, `frontend/`, `db/`, `docker-compose.yml`; Flask app factory + blueprints + SQLAlchemy pool + Alembic; new schema (users/roles, listings, addresses, photos, amenities) + data migration from old tables + seed script.
3. **Phase 2, public marketplace:** `v_public_listings`, `SearchListings` (full-text + spatial + filters + keyset pagination), Next.js home/search/map/detail pages, no login required to browse.
4. **Phase 3, accounts & interactions:** JWT auth, email verification, secure reset, MFA; wishlists, inquiries/messages, viewings, offers.
5. **Phase 4, stays & payments:** availability, `CreateBooking` with overlap protection, Stripe test mode, reviews + rating trigger.
6. **Phase 5, host & admin dashboards:** analytics views/window functions, moderation queue, audit log, encrypted backups.
7. **Phase 6, encryption depth & scale:** envelope encryption with key rotation + blind indexes, InnoDB TDE, TLS to MySQL, Redis cache, read replica, load tests, deploy + CI.

## Execution order after approval
1. Save this plan in the repo as **`docs/PLAN.md`** (the project notes).
2. Create the system design image (section 9).
3. Carry out Phase 0 (fix & secure), commit it, then move through Phases 1→6, committing after each phase on a feature branch (`feature/marketplace`). Commits stay local; nothing is pushed unless you ask.

## 9. System design image (first deliverable after approval)
Create **`docs/system-design.svg`** (hand-written SVG, so it stays crisp on GitHub and in dark/light mode) plus a **`docs/system-design.png`** export (via `rsvg-convert` or `cairosvg` if installed; if neither is, I'll say so and only commit the SVG). Link it from a new `README.md` "Architecture" section.

The diagram contains, left to right:
1. **Clients:** Public visitor, Guest, Host, Admin (browser/mobile).
2. **Edge:** CDN, Nginx reverse proxy / load balancer (TLS 1.3, HSTS, rate limit).
3. **Frontend:** Next.js (SSR/ISR public listings, host & admin dashboards).
4. **API tier:** N × Flask API containers (Gunicorn) with modules: Auth (Argon2id, JWT + refresh, TOTP MFA), RBAC, Listings/Search, Bookings, Inquiries/Messages, Reviews, Admin, Media; plus a **Crypto service** box (AES-256-GCM envelope encryption, HMAC blind index) talking to **KMS/Vault** (master key, rotation).
5. **Data tier:** MySQL 8 primary (procedures, triggers, views, events, InnoDB TDE, TLS-only, least-privilege users) → async replication → read replica (search/analytics); Redis (cache, sessions, rate limits, queue); S3/MinIO (photos, KYC docs, SSE-KMS).
6. **Async:** Celery/RQ workers (email, image resize, search alerts, encrypted backups → backup bucket); Stripe (test mode) webhook.
7. **Observability:** logs, Sentry, Prometheus.
Arrows labelled with protocol/security (HTTPS, TLS, signed URLs), a legend marking encrypted links and encrypted-at-rest stores, and a small inset of the core ER diagram (users, listings, addresses, bookings, offers, transactions, reviews, audit_log).

## Critical files
- Replace: `real_estate_codebase/dbconnection.py` (→ pooled engine), `app.py` (→ factory + blueprints), `client.py`/`agent.py`/`property.py`/`transaction.py` (→ services/repositories), all `templates/*` (→ Next.js app).
- Rewrite: `real_estate.sql` → `db/migrations/*` + `db/procedures/*.sql`, `db/triggers/*.sql`, `db/views/*.sql`, `db/seed/`.
- Reuse/evolve: `GetProperties`/`FilterProperties` → `SearchListings`/host listing query; `after_property_sold` → `CompleteSale` + audit trigger; CSVs → seed input.
- New: `.env.example`, `docker-compose.yml`, `backend/app/security/{passwords,crypto,tokens,rbac}.py`, `frontend/`.

## Verification
- `docker compose up` brings up MySQL, Redis, MinIO, API and frontend; `alembic upgrade head` + seed loads 50k listings.
- Pytest suite: auth (hash stored, never plaintext; reset token single-use/expired), RBAC (guest can't edit, host can't edit others' listings, admin-only endpoints), booking overlap (two concurrent requests → one succeeds), `CompleteSale` rollback on failure, encryption round-trip + key rotation, blind-index lookup.
- Verify in MySQL: `SELECT phone_enc FROM user_profiles` shows ciphertext; `SHOW STATUS LIKE 'Ssl_cipher'` non-empty; `information_schema.INNODB_TABLESPACES` shows encryption; app user lacks DROP privileges.
- Browser: browse/search/map logged-out; sign up → wishlist → book → review; host creates listing → admin approves → appears publicly.
- `EXPLAIN ANALYZE` on search queries uses the composite/spatial/full-text indexes; k6/Locust run at e.g. 200 concurrent users with p95 < 300 ms on search.
- OWASP ZAP baseline scan and `pip-audit`/`npm audit` clean.
