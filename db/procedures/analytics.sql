-- Analytics for host and admin dashboards: CTEs and window functions.
-- These are read-only and are called on the read replica when one is configured.

DROP PROCEDURE IF EXISTS HostEarnings;
DROP PROCEDURE IF EXISTS HostListingPerformance;
DROP PROCEDURE IF EXISTS AdminKpis;
DROP PROCEDURE IF EXISTS AdminMonthlyGmv;
DROP PROCEDURE IF EXISTS AdminTopHosts;
DROP PROCEDURE IF EXISTS AdminCityStats;

DELIMITER $$

-- Last 12 months of host payouts with a running total. A recursive CTE produces
-- every month so months without revenue still appear as zero.
CREATE PROCEDURE HostEarnings(IN p_host_id BIGINT UNSIGNED)
BEGIN
    WITH RECURSIVE months (m) AS (
        SELECT DATE_FORMAT(CURDATE() - INTERVAL 11 MONTH, '%Y-%m-01')
        UNION ALL
        SELECT DATE_FORMAT(m + INTERVAL 1 MONTH, '%Y-%m-01') FROM months WHERE m < DATE_FORMAT(CURDATE(), '%Y-%m-01')
    ),
    monthly AS (
        SELECT DATE_FORMAT(t.created_at, '%Y-%m-01') AS m,
               SUM(t.amount - t.refunded - t.service_fee) AS gross,
               SUM(t.commission) AS commission,
               COUNT(*) AS deals
          FROM transactions t
         WHERE t.host_id = p_host_id AND t.created_at >= CURDATE() - INTERVAL 12 MONTH
         GROUP BY 1
    )
    SELECT DATE_FORMAT(months.m, '%Y-%m') AS month,
           COALESCE(monthly.gross, 0) AS gross,
           COALESCE(monthly.commission, 0) AS commission,
           COALESCE(monthly.gross - monthly.commission, 0) AS payout,
           COALESCE(monthly.deals, 0) AS deals,
           SUM(COALESCE(monthly.gross - monthly.commission, 0)) OVER (ORDER BY months.m) AS running_payout
      FROM months LEFT JOIN monthly ON monthly.m = months.m
     ORDER BY months.m;
END$$

-- Per-listing funnel: views -> favourites -> bookings, occupancy over the last
-- 90 days, 12-month revenue and its rank within the host's portfolio.
CREATE PROCEDURE HostListingPerformance(IN p_host_id BIGINT UNSIGNED)
BEGIN
    WITH booked AS (
        SELECT b.listing_id,
               COUNT(*) AS bookings_90d,
               SUM(DATEDIFF(LEAST(b.check_out, CURDATE()), GREATEST(b.check_in, CURDATE() - INTERVAL 90 DAY))) AS nights_90d
          FROM bookings b
         WHERE b.host_id = p_host_id AND b.status IN ('confirmed','completed')
           AND b.check_out > CURDATE() - INTERVAL 90 DAY AND b.check_in < CURDATE()
         GROUP BY b.listing_id
    ),
    revenue AS (
        SELECT listing_id, SUM(amount - refunded - service_fee - commission) AS payout_12m
          FROM transactions
         WHERE host_id = p_host_id AND created_at >= CURDATE() - INTERVAL 12 MONTH
         GROUP BY listing_id
    )
    SELECT l.public_id, l.title, l.listing_mode, l.status, l.price, l.price_unit, l.city,
           s.views, s.favorites, s.review_count, s.rating_avg,
           COALESCE(bk.bookings_90d, 0) AS bookings_90d,
           IF(l.listing_mode = 'short_term_stay', ROUND(COALESCE(bk.nights_90d, 0) / 90 * 100, 1), NULL) AS occupancy_pct,
           ROUND(COALESCE(bk.bookings_90d, 0) / NULLIF(s.views, 0) * 100, 2) AS conversion_pct,
           COALESCE(r.payout_12m, 0) AS payout_12m,
           RANK() OVER (ORDER BY COALESCE(r.payout_12m, 0) DESC) AS revenue_rank
      FROM listings l
      JOIN listing_stats s ON s.listing_id = l.id
      LEFT JOIN booked bk ON bk.listing_id = l.id
      LEFT JOIN revenue r ON r.listing_id = l.id
     WHERE l.host_id = p_host_id AND l.deleted_at IS NULL
     ORDER BY revenue_rank, l.id DESC
     LIMIT 200;
END$$

CREATE PROCEDURE AdminKpis()
BEGIN
    SELECT
        (SELECT COUNT(*) FROM users WHERE status = 'active') AS active_users,
        (SELECT COUNT(*) FROM users WHERE created_at >= CURDATE() - INTERVAL 30 DAY) AS new_users_30d,
        (SELECT COUNT(DISTINCT user_id) FROM user_roles WHERE role = 'host') AS hosts,
        (SELECT COUNT(*) FROM listings WHERE status = 'published') AS published_listings,
        (SELECT COUNT(*) FROM listings WHERE status = 'pending_review') AS pending_review,
        (SELECT COUNT(*) FROM host_profiles WHERE verification_status = 'pending') AS pending_hosts,
        (SELECT COUNT(*) FROM reports WHERE status = 'open') AS open_reports,
        (SELECT COUNT(*) FROM bookings WHERE status = 'confirmed' AND check_in >= CURDATE()) AS upcoming_stays,
        (SELECT COALESCE(SUM(amount - refunded), 0) FROM transactions WHERE created_at >= CURDATE() - INTERVAL 30 DAY) AS gmv_30d,
        (SELECT COALESCE(SUM(commission + service_fee), 0) FROM transactions WHERE created_at >= CURDATE() - INTERVAL 30 DAY) AS revenue_30d;
END$$

-- Gross merchandise value and platform revenue per month and kind, with
-- month-over-month growth computed by LAG over each kind's own series.
CREATE PROCEDURE AdminMonthlyGmv()
BEGIN
    WITH monthly AS (
        SELECT DATE_FORMAT(created_at, '%Y-%m') AS month, kind,
               SUM(amount - refunded) AS gmv,
               SUM(commission + service_fee) AS platform_revenue,
               COUNT(*) AS deals
          FROM transactions
         WHERE created_at >= DATE_FORMAT(CURDATE() - INTERVAL 11 MONTH, '%Y-%m-01') AND created_at <= NOW()
         GROUP BY 1, 2
    )
    SELECT month, kind, gmv, platform_revenue, deals,
           ROUND((gmv - LAG(gmv) OVER w) / NULLIF(LAG(gmv) OVER w, 0) * 100, 1) AS gmv_growth_pct
      FROM monthly
    WINDOW w AS (PARTITION BY kind ORDER BY month)
     ORDER BY month, kind;
END$$

-- Hosts ranked by 12-month platform revenue, with each host's share of the total.
CREATE PROCEDURE AdminTopHosts()
BEGIN
    SELECT u.public_id, p.display_name AS name, h.verification_status,
           t.deals, t.gmv, t.platform_revenue,
           ROUND(t.platform_revenue / SUM(t.platform_revenue) OVER () * 100, 2) AS share_pct,
           DENSE_RANK() OVER (ORDER BY t.platform_revenue DESC) AS rnk
      FROM (SELECT host_id, COUNT(*) AS deals, SUM(amount - refunded) AS gmv,
                   SUM(commission + service_fee) AS platform_revenue
              FROM transactions WHERE created_at >= CURDATE() - INTERVAL 12 MONTH
             GROUP BY host_id) t
      JOIN users u ON u.id = t.host_id
      JOIN user_profiles p ON p.user_id = u.id
      LEFT JOIN host_profiles h ON h.user_id = u.id
     ORDER BY rnk
     LIMIT 10;
END$$

-- Median nightly price per city, computed with ROW_NUMBER and COUNT windows
-- (MySQL has no MEDIAN aggregate), plus average rating.
CREATE PROCEDURE AdminCityStats()
BEGIN
    WITH ranked AS (
        SELECT l.city, l.price, s.rating_avg,
               ROW_NUMBER() OVER (PARTITION BY l.city ORDER BY l.price) AS rn,
               COUNT(*) OVER (PARTITION BY l.city) AS n
          FROM listings l JOIN listing_stats s ON s.listing_id = l.id
         WHERE l.status = 'published' AND l.listing_mode = 'short_term_stay'
    )
    SELECT city, MAX(n) AS listings,
           ROUND(AVG(CASE WHEN rn IN (FLOOR((n + 1) / 2), CEIL((n + 1) / 2)) THEN price END), 2) AS median_nightly,
           ROUND(AVG(rating_avg), 2) AS avg_rating
      FROM ranked
     GROUP BY city
     ORDER BY median_nightly DESC;
END$$

DELIMITER ;
