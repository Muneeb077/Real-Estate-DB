-- Stay pricing and the booking lifecycle: quote -> hold (pending) -> pay (confirmed)
-- -> completed, or cancelled / expired. Every state change locks the rows it reads.

DROP FUNCTION IF EXISTS CalcStaySubtotal;
DROP PROCEDURE IF EXISTS QuoteStay;
DROP PROCEDURE IF EXISTS CreateBooking;
DROP PROCEDURE IF EXISTS ConfirmBooking;
DROP PROCEDURE IF EXISTS CancelBooking;

DELIMITER $$

-- Sum of nightly prices for [p_in, p_out). A recursive CTE expands the stay into
-- one row per night; each night takes the most specific matching price rule
-- (weekend rules apply to Friday and Saturday nights) or the base price.
CREATE FUNCTION CalcStaySubtotal(p_listing_id BIGINT UNSIGNED, p_in DATE, p_out DATE)
RETURNS DECIMAL(12,2)
READS SQL DATA
BEGIN
    DECLARE v_total DECIMAL(12,2);
    WITH RECURSIVE nights (d) AS (
        SELECT p_in
        UNION ALL
        SELECT d + INTERVAL 1 DAY FROM nights WHERE d + INTERVAL 1 DAY < p_out
    )
    SELECT SUM(COALESCE(
        (SELECT r.nightly_price FROM price_rules r
          WHERE r.listing_id = p_listing_id
            AND n.d BETWEEN r.start_date AND r.end_date
            AND (r.weekends_only = FALSE OR DAYOFWEEK(n.d) IN (6, 7))
          ORDER BY DATEDIFF(r.end_date, r.start_date), r.id
          LIMIT 1),
        l.price))
      INTO v_total
      FROM nights n
      JOIN listings l ON l.id = p_listing_id;
    RETURN v_total;
END$$

CREATE PROCEDURE QuoteStay(
    IN p_listing_id BIGINT UNSIGNED, IN p_in DATE, IN p_out DATE, IN p_guests INT)
BEGIN
    DECLARE v_fee_rate DECIMAL(5,4);
    DECLARE v_subtotal DECIMAL(12,2);
    DECLARE v_reason VARCHAR(100) DEFAULT NULL;
    DECLARE v_max INT;

    SELECT CAST(JSON_UNQUOTE(v) AS DECIMAL(5,4)) INTO v_fee_rate FROM settings WHERE k = 'service_fee_rate';
    SELECT max_guests INTO v_max FROM listings WHERE id = p_listing_id;

    IF p_out <= p_in OR DATEDIFF(p_out, p_in) > 90 THEN
        SET v_reason = 'Stays are 1 to 90 nights.';
    ELSEIF p_in < CURDATE() THEN
        SET v_reason = 'Check-in is in the past.';
    ELSEIF p_guests > v_max THEN
        SET v_reason = CONCAT('This place fits up to ', v_max, ' guests.');
    ELSEIF EXISTS (SELECT 1 FROM blocked_dates WHERE listing_id = p_listing_id AND day >= p_in AND day < p_out) THEN
        SET v_reason = 'The host has blocked some of those dates.';
    ELSEIF EXISTS (SELECT 1 FROM bookings b
                    WHERE b.listing_id = p_listing_id
                      AND (b.status = 'confirmed' OR (b.status = 'pending' AND b.hold_expires_at > NOW()))
                      AND b.check_in < p_out AND b.check_out > p_in) THEN
        SET v_reason = 'Those dates are already booked.';
    END IF;

    IF p_out > p_in AND DATEDIFF(p_out, p_in) <= 90 THEN
        SET v_subtotal = CalcStaySubtotal(p_listing_id, p_in, p_out);
    END IF;

    SELECT DATEDIFF(p_out, p_in) AS nights,
           v_subtotal AS subtotal,
           ROUND(v_subtotal * v_fee_rate, 2) AS service_fee,
           v_subtotal + ROUND(v_subtotal * v_fee_rate, 2) AS total,
           v_reason IS NULL AS available,
           v_reason AS reason;
END$$

-- Places a 30-minute hold on the dates. The listing row lock serialises
-- concurrent attempts on the same listing, so exactly one of two simultaneous
-- requests for overlapping dates succeeds. Idempotency-Key makes retries safe.
CREATE PROCEDURE CreateBooking(
    IN p_listing_id BIGINT UNSIGNED, IN p_guest_id BIGINT UNSIGNED, IN p_in DATE, IN p_out DATE,
    IN p_guests INT, IN p_public_id CHAR(26), IN p_idem VARCHAR(64))
BEGIN
    DECLARE v_host BIGINT UNSIGNED;
    DECLARE v_status VARCHAR(20);
    DECLARE v_mode VARCHAR(20);
    DECLARE v_max INT;
    DECLARE v_currency CHAR(3);
    DECLARE v_subtotal DECIMAL(12,2);
    DECLARE v_fee DECIMAL(12,2);
    DECLARE v_hold INT;
    DECLARE v_existing BIGINT UNSIGNED;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SELECT id INTO v_existing FROM bookings WHERE guest_id = p_guest_id AND idempotency_key = p_idem;
    IF v_existing IS NOT NULL THEN
        SELECT public_id, status, total_price, hold_expires_at FROM bookings WHERE id = v_existing;
    ELSE
        START TRANSACTION;

        SELECT host_id, status, listing_mode, max_guests, currency
          INTO v_host, v_status, v_mode, v_max, v_currency
          FROM listings WHERE id = p_listing_id
          FOR UPDATE;

        IF v_status IS NULL OR v_status <> 'published' OR v_mode <> 'short_term_stay' THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'This place is not available to book.';
        END IF;
        IF v_host = p_guest_id THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'You can''t book your own listing.';
        END IF;
        IF p_in < CURDATE() OR p_out <= p_in OR DATEDIFF(p_out, p_in) > 90 THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Choose a stay of 1 to 90 nights starting today or later.';
        END IF;
        IF p_guests < 1 OR p_guests > v_max THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Too many guests for this place.';
        END IF;
        IF EXISTS (SELECT 1 FROM blocked_dates WHERE listing_id = p_listing_id AND day >= p_in AND day < p_out) THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'The host has blocked some of those dates.';
        END IF;
        IF EXISTS (SELECT 1 FROM bookings b
                    WHERE b.listing_id = p_listing_id
                      AND (b.status = 'confirmed' OR (b.status = 'pending' AND b.hold_expires_at > NOW()))
                      AND b.check_in < p_out AND b.check_out > p_in) THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Those dates are no longer available.';
        END IF;

        SELECT CAST(JSON_UNQUOTE(v) AS UNSIGNED) INTO v_hold FROM settings WHERE k = 'booking_hold_minutes';
        SET v_subtotal = CalcStaySubtotal(p_listing_id, p_in, p_out);
        SELECT ROUND(v_subtotal * CAST(JSON_UNQUOTE(v) AS DECIMAL(5,4)), 2) INTO v_fee
          FROM settings WHERE k = 'service_fee_rate';

        INSERT INTO bookings (public_id, listing_id, guest_id, host_id, check_in, check_out, guests,
                              subtotal, service_fee, total_price, currency, status, hold_expires_at, idempotency_key)
        VALUES (p_public_id, p_listing_id, p_guest_id, v_host, p_in, p_out, p_guests,
                v_subtotal, v_fee, v_subtotal + v_fee, v_currency, 'pending',
                NOW() + INTERVAL COALESCE(v_hold, 30) MINUTE, p_idem);

        COMMIT;
        SELECT public_id, status, total_price, hold_expires_at FROM bookings WHERE public_id = p_public_id;
    END IF;
END$$

-- Called after a successful payment (simulated, or the Stripe webhook).
-- Idempotent: a repeated webhook for the same payment changes nothing.
CREATE PROCEDURE ConfirmBooking(
    IN p_booking_id BIGINT UNSIGNED, IN p_provider VARCHAR(20), IN p_ref VARCHAR(255))
BEGIN
    DECLARE v_status VARCHAR(20);
    DECLARE v_hold DATETIME;
    DECLARE v_listing BIGINT UNSIGNED;
    DECLARE v_guest BIGINT UNSIGNED;
    DECLARE v_host BIGINT UNSIGNED;
    DECLARE v_subtotal DECIMAL(12,2);
    DECLARE v_fee DECIMAL(12,2);
    DECLARE v_total DECIMAL(12,2);
    DECLARE v_currency CHAR(3);
    DECLARE v_rate DECIMAL(5,4);
    DECLARE v_title VARCHAR(140);
    DECLARE v_pid CHAR(26);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    SELECT b.status, b.hold_expires_at, b.listing_id, b.guest_id, b.host_id, b.subtotal, b.service_fee,
           b.total_price, b.currency, l.title, b.public_id
      INTO v_status, v_hold, v_listing, v_guest, v_host, v_subtotal, v_fee, v_total, v_currency, v_title, v_pid
      FROM bookings b JOIN listings l ON l.id = b.listing_id
     WHERE b.id = p_booking_id
       FOR UPDATE;

    IF v_status = 'confirmed' AND EXISTS (SELECT 1 FROM payments WHERE booking_id = p_booking_id
                                                                     AND provider = p_provider AND provider_ref = p_ref) THEN
        COMMIT;  -- duplicate delivery of the same payment
    ELSE
        IF v_status IS NULL OR v_status <> 'pending' OR v_hold < NOW() THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'This reservation hold has expired. Please book again.';
        END IF;

        SELECT COALESCE(h.commission_rate, CAST(JSON_UNQUOTE(s.v) AS DECIMAL(5,4)))
          INTO v_rate
          FROM settings s LEFT JOIN host_profiles h ON h.user_id = v_host
         WHERE s.k = 'default_commission_rate';

        UPDATE bookings SET status = 'confirmed', hold_expires_at = NULL WHERE id = p_booking_id;
        INSERT INTO payments (booking_id, provider, provider_ref, amount)
        VALUES (p_booking_id, p_provider, p_ref, v_total);
        INSERT INTO transactions (kind, listing_id, host_id, guest_id, booking_id, amount, commission, service_fee, currency)
        VALUES ('stay', v_listing, v_host, v_guest, p_booking_id, v_total, ROUND(v_subtotal * v_rate, 2), v_fee, v_currency);
        INSERT INTO notifications (user_id, kind, title, link) VALUES
            (v_guest, 'booking_confirmed', CONCAT('Your stay at "', v_title, '" is confirmed'), CONCAT('/trips/', v_pid)),
            (v_host, 'booking_received', CONCAT('New booking for "', v_title, '"'), '/host/bookings');
        COMMIT;
    END IF;

    SELECT public_id, status FROM bookings WHERE id = p_booking_id;
END$$

-- Cancellation policy:
--   host or admin cancels            -> full refund
--   guest, 7+ days before check-in   -> full refund
--   guest, less than 7 days before   -> 50% of the nightly subtotal; service fee not refunded
CREATE PROCEDURE CancelBooking(
    IN p_booking_id BIGINT UNSIGNED, IN p_actor_id BIGINT UNSIGNED, IN p_actor_role VARCHAR(10))
BEGIN
    DECLARE v_status VARCHAR(20);
    DECLARE v_guest BIGINT UNSIGNED;
    DECLARE v_host BIGINT UNSIGNED;
    DECLARE v_in DATE;
    DECLARE v_subtotal DECIMAL(12,2);
    DECLARE v_total DECIMAL(12,2);
    DECLARE v_title VARCHAR(140);
    DECLARE v_by VARCHAR(10);
    DECLARE v_refund DECIMAL(12,2) DEFAULT 0;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    SELECT b.status, b.guest_id, b.host_id, b.check_in, b.subtotal, b.total_price, l.title
      INTO v_status, v_guest, v_host, v_in, v_subtotal, v_total, v_title
      FROM bookings b JOIN listings l ON l.id = b.listing_id
     WHERE b.id = p_booking_id
       FOR UPDATE;

    SET v_by = CASE
        WHEN p_actor_role = 'admin' THEN 'admin'
        WHEN p_actor_id = v_guest THEN 'guest'
        WHEN p_actor_id = v_host THEN 'host'
    END;
    IF v_status IS NULL OR v_by IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Booking not found.';
    END IF;
    IF v_status NOT IN ('pending','confirmed') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'This booking can no longer be cancelled.';
    END IF;
    IF v_in <= CURDATE() AND v_by <> 'admin' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Stays can''t be cancelled on or after check-in day.';
    END IF;

    IF v_status = 'confirmed' THEN
        SET v_refund = CASE
            WHEN v_by IN ('host','admin') THEN v_total
            WHEN DATEDIFF(v_in, CURDATE()) >= 7 THEN v_total
            ELSE ROUND(v_subtotal * 0.5, 2)
        END;
        UPDATE payments
           SET refunded = v_refund, status = IF(v_refund = amount, 'refunded', 'partially_refunded')
         WHERE booking_id = p_booking_id;
        UPDATE transactions SET refunded = v_refund WHERE booking_id = p_booking_id;
    END IF;

    UPDATE bookings
       SET status = 'cancelled', cancelled_by = v_by, cancelled_at = NOW(), refund_amount = v_refund,
           hold_expires_at = NULL
     WHERE id = p_booking_id;

    INSERT INTO notifications (user_id, kind, title, link)
    SELECT IF(v_by = 'guest', v_host, v_guest), 'booking_cancelled',
           CONCAT('Booking for "', v_title, '" was cancelled by the ', v_by),
           IF(v_by = 'guest', '/host/bookings', '/trips')
     WHERE v_status = 'confirmed';

    COMMIT;
    SELECT v_refund AS refund_amount, v_by AS cancelled_by;
END$$

DELIMITER ;
