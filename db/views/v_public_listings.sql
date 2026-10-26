-- The only listing source the public API reads from: published, not deleted,
-- and without private columns. Coordinates are rounded to 3 decimals (~100 m)
-- so the exact address is never exposed. address_id is kept for spatial joins
-- inside SearchListings and is never returned by the API.
--
-- The cover photo is a JOIN (sort_order 0), not a correlated subquery: subqueries
-- in a view's select list make MySQL materialise the whole view (TEMPTABLE)
-- instead of merging it into the outer query, which defeats every index.
-- Repeatable: re-applied by later migrations when it changes.
CREATE OR REPLACE SQL SECURITY INVOKER VIEW v_public_listings AS
SELECT
    l.id,
    l.public_id,
    l.title,
    l.listing_mode,
    l.property_type,
    l.bedrooms,
    l.bathrooms,
    l.max_guests,
    l.size_sqft,
    l.price,
    l.currency,
    l.price_unit,
    l.city,
    a.state,
    a.country,
    ROUND(ST_Latitude(a.location), 3)  AS lat,
    ROUND(ST_Longitude(a.location), 3) AS lng,
    cp.url AS cover_url,
    cp.thumb_url AS cover_thumb_url,
    s.rating_avg,
    COALESCE(s.review_count, 0) AS review_count,
    l.published_at,
    l.host_id,
    l.address_id
FROM listings l
JOIN addresses a ON a.id = l.address_id
LEFT JOIN listing_stats s ON s.listing_id = l.id
LEFT JOIN listing_photos cp ON cp.listing_id = l.id AND cp.sort_order = 0
WHERE l.status = 'published' AND l.deleted_at IS NULL;
