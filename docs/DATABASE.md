# Database design

MySQL 8.0+ (developed on 9.3), InnoDB, utf8mb4. All SQL is hand-written in `db/` and applied in order by Alembic (`backend/migrations/versions/000N_*.py`). The same files also run with `mysql < file.sql`.

| Migration | Adds |
|---|---|
| `0001_core` | users, roles, profiles, host profiles, addresses (SPATIAL), listings (FULLTEXT, composite indexes, CHECKs), photos, amenities, stats, settings, audit log; denormalisation and version triggers |
| `0002_search` | `v_public_listings` view, `SearchListings` procedure |
| `0003_accounts` | refresh/one-time tokens, login attempts, favourites (+ counter triggers), saved searches, conversations/messages, viewings, offers, transactions, notifications, reports; `AcceptOffer`; purge event |
| `0004_stays` | blocked dates, price rules, bookings (generated column), payments, reviews; `CalcStaySubtotal`, `QuoteStay`, `CreateBooking`, `ConfirmBooking`, `CancelBooking`; overlap and review triggers; hold-expiry and completion events; date-aware search |
| `0005_admin` | audit triggers on 8 tables, append-only guard, backups table, analytics procedures |
| `0006_partitioning` | `audit_log` range-partitioned by year, partition maintenance procedure and event |

## Entity overview

```
users ─┬─ user_roles (guest | host | admin, many per user)
       ├─ user_profiles (phone_enc + phone_hash)
       ├─ host_profiles (license_enc, verification, commission_rate)
       └─ refresh_tokens / auth_tokens / login_attempts

listings ── addresses (street_enc, POINT SRID 4326)
   ├─ listing_photos, listing_amenities ── amenities, listing_stats (views, favourites, rating)
   ├─ blocked_dates, price_rules
   ├─ bookings ── payments, reviews
   ├─ offers, viewings, conversations ── messages (body_enc)
   └─ transactions (exactly one of offer_id / booking_id)
```

Design choices worth noting:

- **Surrogate `BIGINT` keys internally, ULID `public_id` externally.** URLs never expose sequential ids, which were enumerable in the legacy app.
- **Many roles per user** (`user_roles`) instead of separate Client/Agent tables, so one person can book and host.
- **Money is `DECIMAL(12,2)`.** `transactions` has `CHECK ((offer_id IS NULL) <> (booking_id IS NULL))` so every row comes from exactly one source.
- **`listings.city` is denormalised** from `addresses` by triggers so the composite index `(status, listing_mode, city, price)` can serve the most common search.
- **Hot counters live in `listing_stats`**, not on the listing row, so view and favourite increments don't contend with edits.
- **`bookings.nights` is a STORED generated column.** CHECKs enforce `check_out > check_in`, at most 90 nights, and `total = subtotal + fee`.

## Stored procedures and functions

| Routine | What it shows |
|---|---|
| `SearchListings` | Dynamic SQL built from only the active filters. Values are embedded with `QUOTE()` and enums and sort keys are whitelisted. It combines InnoDB FULLTEXT (boolean mode), `MBRContains` bounding box and `ST_Distance_Sphere` radius search on the SPATIAL index, `NOT EXISTS` anti-joins for date availability, and keyset pagination (`(sort_value, id)` comparisons, no OFFSET). |
| `CalcStaySubtotal` | A recursive CTE expands a stay into one row per night. Each night takes the most specific price rule (weekend rules only on Friday and Saturday) or the base price. |
| `QuoteStay` | Price breakdown plus an availability verdict with a human-readable reason. |
| `CreateBooking` | `SELECT … FOR UPDATE` on the listing row serialises concurrent bookings for that listing. It validates guests, blocked dates and overlaps, then places a 30-minute hold. Idempotency keys make retries safe. A test fires 4 concurrent requests and asserts that no overlapping bookings survive. |
| `ConfirmBooking` | Idempotent under duplicate payment webhooks. Writes the payment, transaction (commission computed once, here) and notifications in one transaction. |
| `CancelBooking` | Applies the refund policy (host/admin full refund; guest full refund 7+ days out, otherwise 50% of nights) and updates payment, transaction and booking together. |
| `AcceptOffer` | Replaces the legacy `sell_property`, which committed the status change before inserting the transaction and always failed on a NOT NULL id. It locks the offer and listing, accepts one offer, supersedes the rest with notifications, marks the listing sold or rented, and records the transaction atomically. Errors come back as `SIGNAL SQLSTATE '45000'` messages, which the API returns to users as 409s. |
| `HostEarnings` | A recursive CTE generates every month so empty months show 0; running payout via `SUM() OVER (ORDER BY month)`. |
| `HostListingPerformance` | Views → favourites → bookings funnel, 90-day occupancy, 12-month payout, `RANK() OVER` by revenue. |
| `AdminMonthlyGmv` | GMV and platform revenue per month and kind; month-over-month growth with `LAG()` over a named `WINDOW`. |
| `AdminTopHosts` | `DENSE_RANK()`, and each host's share of total via `SUM() OVER ()`. |
| `AdminCityStats` | Median nightly price per city from `ROW_NUMBER()` and `COUNT()` windows (MySQL has no `MEDIAN`). |
| `EnsureAuditPartition`, `DropAuditPartitionsBefore` | Partition maintenance via prepared DDL and a cursor. |

## Triggers

- **Integrity:** `trg_bookings_bi` rejects overlapping active bookings even for writes that bypass the procedure. `trg_reviews_bi` allows a review only for a completed stay by that guest. `trg_listings_bu` bumps `version` for optimistic locking and stamps `published_at`.
- **Derived data:** favourite counters, rating average and count (recomputed on insert and on hide/unhide), city denormalisation, `listing_stats` row creation.
- **Audit:** 8 `AFTER` triggers write `audit_log` rows with old and new values as `JSON_OBJECT`. The actor comes from the `@actor_id` session variable, which the API sets on every connection it uses (`backend/app/db.py`). `trg_audit_no_update` and `trg_audit_no_delete` make the log append-only, even for the application's own account.

## Events (event scheduler)

| Event | Schedule | Job |
|---|---|---|
| `ev_expire_booking_holds` | every minute | unpaid holds become `expired`, freeing the dates |
| `ev_complete_stays` | hourly | finished stays become `completed` and guests are invited to review |
| `ev_purge_auth_data` | hourly | expired tokens and old login attempts are deleted |
| `ev_audit_partitions` | monthly | next year's audit partition is created ahead of time |

## Indexing and performance

- `idx_listings_search (status, listing_mode, city, price)` serves the main search and the city facets.
- `idx_listings_newest (status, published_at, id)` and `idx_listings_price (status, price, id)` match the keyset sort orders.
- `sp_addresses_location` (SPATIAL, SRID 4326) is used by `MBRContains` for map searches: `EXPLAIN` shows a `range` scan on it.
- `ft_listings_text` (FULLTEXT on title and description) serves keyword search.
- `idx_bookings_overlap (listing_id, status, check_in, check_out)` backs both the overlap check and the availability anti-join.

**A view pitfall found and fixed.** The first version of `v_public_listings` fetched the cover photo with correlated subqueries in its select list. That makes MySQL materialise the view (`<derived2>` in `EXPLAIN`) instead of merging it into the outer query. Every search then built a temp table of all ~37k published listings, and a "top rated" query ran for minutes. Replacing the subqueries with a `LEFT JOIN … sort_order = 0` lets the view merge, so `EXPLAIN` shows `SIMPLE` rows driven by `idx_listings_search` and the query takes about 0.2 s. The API keeps photo `sort_order` dense from 0 so the join stays correct.

**Partitioning.** `audit_log` is `PARTITION BY RANGE COLUMNS(created_at)` with yearly partitions. Date-filtered queries prune partitions (`EXPLAIN … partitions: p2026,p2027,pmax`), and retention is `DROP PARTITION`, a metadata operation that also respects the append-only rule, since no rows are deleted.

## Accounts and privileges (`db/security/grants.sql`)

| Account | Rights | Used by |
|---|---|---|
| `homenest_migrator` | DDL on `homenest.*` | Alembic only |
| `homenest_app` | `SELECT, INSERT, UPDATE, EXECUTE`; `DELETE` only on 6 user-owned toggle tables | the API |
| `homenest_ro` | `SELECT, EXECUTE` | read replica / analytics |
| `homenest_backup` | `SELECT, SHOW VIEW, TRIGGER, LOCK TABLES, EVENT, PROCESS` | `mysqldump` for backups |

Every account has `REQUIRE SSL`, and the server runs with `require_secure_transport=ON`.
