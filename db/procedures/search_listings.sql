-- SearchListings: one entry point for the public search page and the map.
--
-- * Builds the WHERE clause dynamically so only active filters reach the optimizer
--   (static "(? IS NULL OR col = ?)" predicates defeat index selection).
-- * Strings are embedded with QUOTE(); enums and sort keys are whitelisted.
-- * Full-text (InnoDB FULLTEXT, boolean mode), map bounding box (SPATIAL index,
--   MBRContains) and radius search (ST_Distance_Sphere) on SRID 4326 points.
-- * Keyset pagination: the caller passes the sort value and id of the last row it
--   saw; no OFFSET scans, stable under concurrent inserts.
-- * p_check_in / p_check_out keep only stays with no overlapping booking or
--   blocked day (anti-join with NOT EXISTS).
-- Repeatable: re-applied by migration 0004 when the bookings tables arrive.
DROP PROCEDURE IF EXISTS SearchListings;

DELIMITER $$

CREATE PROCEDURE SearchListings(
    IN p_q            VARCHAR(200),
    IN p_mode         VARCHAR(20),
    IN p_type         VARCHAR(20),
    IN p_city         VARCHAR(80),
    IN p_min_price    DECIMAL(12,2),
    IN p_max_price    DECIMAL(12,2),
    IN p_min_beds     INT,
    IN p_min_baths    DECIMAL(3,1),
    IN p_guests       INT,
    IN p_amenities    VARCHAR(400),
    IN p_min_lat      DOUBLE,
    IN p_min_lng      DOUBLE,
    IN p_max_lat      DOUBLE,
    IN p_max_lng      DOUBLE,
    IN p_near_lat     DOUBLE,
    IN p_near_lng     DOUBLE,
    IN p_radius_km    DOUBLE,
    IN p_check_in     DATE,
    IN p_check_out    DATE,
    IN p_sort         VARCHAR(20),
    IN p_cursor_value VARCHAR(40),
    IN p_cursor_id    BIGINT,
    IN p_limit        INT
)
BEGIN
    DECLARE v_sort_expr VARCHAR(100);
    DECLARE v_dir       VARCHAR(4);
    DECLARE v_cmp       CHAR(1);
    DECLARE v_amenity_n INT;

    IF p_mode IS NOT NULL AND p_mode NOT IN ('sale','long_term_rent','short_term_stay') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Unknown listing mode.';
    END IF;
    IF p_type IS NOT NULL AND p_type NOT IN ('house','apartment','condo','townhouse','villa','cabin','studio','loft') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Unknown property type.';
    END IF;

    CASE COALESCE(p_sort, 'newest')
        WHEN 'newest'     THEN SET v_sort_expr = 'v.published_at', v_dir = 'DESC';
        WHEN 'price_asc'  THEN SET v_sort_expr = 'v.price',        v_dir = 'ASC';
        WHEN 'price_desc' THEN SET v_sort_expr = 'v.price',        v_dir = 'DESC';
        WHEN 'rating'     THEN SET v_sort_expr = 'COALESCE(v.rating_avg, 0)', v_dir = 'DESC';
        ELSE SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Unknown sort order.';
    END CASE;
    SET v_cmp = IF(v_dir = 'ASC', '>', '<');

    SET @sql = CONCAT(
        'SELECT v.id, v.public_id, v.title, v.listing_mode, v.property_type, v.bedrooms, v.bathrooms, ',
        'v.max_guests, v.size_sqft, v.price, v.currency, v.price_unit, v.city, v.state, v.country, ',
        'v.lat, v.lng, v.cover_url, v.cover_thumb_url, v.rating_avg, v.review_count, v.published_at, ',
        'CAST(', v_sort_expr, ' AS CHAR) AS sort_value ',
        'FROM v_public_listings v ');

    IF p_q IS NOT NULL AND p_q <> '' THEN
        SET @sql = CONCAT(@sql, 'JOIN listings ft ON ft.id = v.id AND MATCH(ft.title, ft.description) AGAINST (',
                          QUOTE(p_q), ' IN BOOLEAN MODE) ');
    END IF;
    IF p_min_lat IS NOT NULL OR p_near_lat IS NOT NULL THEN
        SET @sql = CONCAT(@sql, 'JOIN addresses ga ON ga.id = v.address_id ');
    END IF;

    SET @sql = CONCAT(@sql, 'WHERE 1 = 1');

    IF p_mode  IS NOT NULL THEN SET @sql = CONCAT(@sql, ' AND v.listing_mode = ', QUOTE(p_mode)); END IF;
    IF p_type  IS NOT NULL THEN SET @sql = CONCAT(@sql, ' AND v.property_type = ', QUOTE(p_type)); END IF;
    IF p_city  IS NOT NULL THEN SET @sql = CONCAT(@sql, ' AND v.city = ', QUOTE(p_city)); END IF;
    IF p_min_price IS NOT NULL THEN SET @sql = CONCAT(@sql, ' AND v.price >= ', p_min_price); END IF;
    IF p_max_price IS NOT NULL THEN SET @sql = CONCAT(@sql, ' AND v.price <= ', p_max_price); END IF;
    IF p_min_beds  IS NOT NULL THEN SET @sql = CONCAT(@sql, ' AND v.bedrooms >= ', p_min_beds); END IF;
    IF p_min_baths IS NOT NULL THEN SET @sql = CONCAT(@sql, ' AND v.bathrooms >= ', p_min_baths); END IF;
    IF p_guests    IS NOT NULL THEN SET @sql = CONCAT(@sql, ' AND v.max_guests >= ', p_guests); END IF;

    IF p_amenities IS NOT NULL AND p_amenities <> '' THEN
        SET v_amenity_n = LENGTH(p_amenities) - LENGTH(REPLACE(p_amenities, ',', '')) + 1;
        SET @sql = CONCAT(@sql,
            ' AND v.id IN (SELECT la.listing_id FROM listing_amenities la',
            ' JOIN amenities am ON am.id = la.amenity_id',
            ' WHERE FIND_IN_SET(am.code, ', QUOTE(p_amenities), ')',
            ' GROUP BY la.listing_id HAVING COUNT(*) = ', v_amenity_n, ')');
    END IF;

    IF p_min_lat IS NOT NULL THEN
        SET @sql = CONCAT(@sql, ' AND MBRContains(ST_GeomFromText(''POLYGON((',
            p_min_lat, ' ', p_min_lng, ', ', p_min_lat, ' ', p_max_lng, ', ',
            p_max_lat, ' ', p_max_lng, ', ', p_max_lat, ' ', p_min_lng, ', ',
            p_min_lat, ' ', p_min_lng, '))'', 4326), ga.location)');
    END IF;
    IF p_near_lat IS NOT NULL THEN
        SET @sql = CONCAT(@sql, ' AND ST_Distance_Sphere(ga.location, ST_GeomFromText(''POINT(',
            p_near_lat, ' ', p_near_lng, ')'', 4326)) <= ', COALESCE(p_radius_km, 10) * 1000);
    END IF;

    IF p_check_in IS NOT NULL AND p_check_out IS NOT NULL THEN
        SET @sql = CONCAT(@sql,
            ' AND v.listing_mode = ''short_term_stay''',
            ' AND NOT EXISTS (SELECT 1 FROM bookings b WHERE b.listing_id = v.id',
            ' AND (b.status = ''confirmed'' OR (b.status = ''pending'' AND b.hold_expires_at > NOW()))',
            ' AND b.check_in < ', QUOTE(p_check_out), ' AND b.check_out > ', QUOTE(p_check_in), ')',
            ' AND NOT EXISTS (SELECT 1 FROM blocked_dates bd WHERE bd.listing_id = v.id',
            ' AND bd.day >= ', QUOTE(p_check_in), ' AND bd.day < ', QUOTE(p_check_out), ')');
    END IF;

    IF p_cursor_id IS NOT NULL THEN
        SET @sql = CONCAT(@sql, ' AND (', v_sort_expr, ' ', v_cmp, ' ', QUOTE(p_cursor_value),
            ' OR (', v_sort_expr, ' = ', QUOTE(p_cursor_value), ' AND v.id ', v_cmp, ' ', p_cursor_id, '))');
    END IF;

    SET @sql = CONCAT(@sql, ' ORDER BY ', v_sort_expr, ' ', v_dir, ', v.id ', v_dir,
                      ' LIMIT ', LEAST(GREATEST(COALESCE(p_limit, 24), 1), 101));

    PREPARE stmt FROM @sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
END$$

DELIMITER ;
