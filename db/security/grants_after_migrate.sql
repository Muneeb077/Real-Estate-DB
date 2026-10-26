-- Run after `alembic upgrade head`. The app may hard-delete only rows that are
-- user-owned toggles; everything else is soft-deleted or kept for audit.
GRANT DELETE ON homenest.favorites TO 'homenest_app'@'%';
GRANT DELETE ON homenest.saved_searches TO 'homenest_app'@'%';
GRANT DELETE ON homenest.listing_amenities TO 'homenest_app'@'%';
GRANT DELETE ON homenest.listing_photos TO 'homenest_app'@'%';
GRANT DELETE ON homenest.blocked_dates TO 'homenest_app'@'%';
GRANT DELETE ON homenest.price_rules TO 'homenest_app'@'%';
