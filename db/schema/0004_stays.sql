-- =====================================================================
-- 0004 short-term stays: availability, nightly pricing, bookings,
-- payments, reviews.
-- =====================================================================

-- Days a host has closed on the calendar.
CREATE TABLE blocked_dates (
    listing_id  BIGINT UNSIGNED NOT NULL,
    day         DATE NOT NULL,
    PRIMARY KEY (listing_id, day),
    CONSTRAINT fk_blocked_listing FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Seasonal / weekend overrides of the nightly price. The most specific
-- (shortest) matching rule wins for a night.
CREATE TABLE price_rules (
    id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    listing_id     BIGINT UNSIGNED NOT NULL,
    label          VARCHAR(60) NOT NULL,
    start_date     DATE NOT NULL,
    end_date       DATE NOT NULL,
    nightly_price  DECIMAL(12,2) NOT NULL,
    weekends_only  BOOLEAN NOT NULL DEFAULT FALSE,
    KEY idx_price_rules (listing_id, start_date, end_date),
    CONSTRAINT chk_price_rule_dates CHECK (end_date >= start_date),
    CONSTRAINT chk_price_rule_price CHECK (nightly_price > 0),
    CONSTRAINT fk_price_rules_listing FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE bookings (
    id               BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    public_id        CHAR(26) NOT NULL,
    listing_id       BIGINT UNSIGNED NOT NULL,
    guest_id         BIGINT UNSIGNED NOT NULL,
    host_id          BIGINT UNSIGNED NOT NULL,
    check_in         DATE NOT NULL,
    check_out        DATE NOT NULL,
    nights           SMALLINT UNSIGNED AS (DATEDIFF(check_out, check_in)) STORED,
    guests           TINYINT UNSIGNED NOT NULL,
    subtotal         DECIMAL(12,2) NOT NULL,
    service_fee      DECIMAL(12,2) NOT NULL,
    total_price      DECIMAL(12,2) NOT NULL,
    currency         CHAR(3) NOT NULL DEFAULT 'USD',
    status           ENUM('pending','confirmed','cancelled','completed','expired') NOT NULL DEFAULT 'pending',
    hold_expires_at  DATETIME NULL,
    idempotency_key  VARCHAR(64) NULL,
    cancelled_by     ENUM('guest','host','admin') NULL,
    cancelled_at     DATETIME NULL,
    refund_amount    DECIMAL(12,2) NULL,
    created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_bookings_public (public_id),
    UNIQUE KEY uq_bookings_idempotency (guest_id, idempotency_key),
    KEY idx_bookings_overlap (listing_id, status, check_in, check_out),
    KEY idx_bookings_guest (guest_id, check_in),
    KEY idx_bookings_host (host_id, check_in),
    KEY idx_bookings_hold (status, hold_expires_at),
    CONSTRAINT chk_booking_dates CHECK (check_out > check_in),
    CONSTRAINT chk_booking_nights CHECK (DATEDIFF(check_out, check_in) <= 90),
    CONSTRAINT chk_booking_guests CHECK (guests >= 1),
    CONSTRAINT chk_booking_total CHECK (total_price = subtotal + service_fee),
    CONSTRAINT fk_bookings_listing FOREIGN KEY (listing_id) REFERENCES listings(id),
    CONSTRAINT fk_bookings_guest FOREIGN KEY (guest_id) REFERENCES users(id),
    CONSTRAINT fk_bookings_host FOREIGN KEY (host_id) REFERENCES users(id)
) ENGINE=InnoDB;

-- Only provider references are stored, never card data.
CREATE TABLE payments (
    id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    booking_id     BIGINT UNSIGNED NOT NULL,
    provider       ENUM('stripe','simulated') NOT NULL,
    provider_ref   VARCHAR(255) NOT NULL,
    amount         DECIMAL(12,2) NOT NULL,
    refunded       DECIMAL(12,2) NOT NULL DEFAULT 0,
    status         ENUM('succeeded','partially_refunded','refunded') NOT NULL DEFAULT 'succeeded',
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_payments_ref (provider, provider_ref),
    UNIQUE KEY uq_payments_booking (booking_id),
    CONSTRAINT chk_payment_refund CHECK (refunded BETWEEN 0 AND amount),
    CONSTRAINT fk_payments_booking FOREIGN KEY (booking_id) REFERENCES bookings(id)
) ENGINE=InnoDB;

CREATE TABLE reviews (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    booking_id  BIGINT UNSIGNED NOT NULL,
    listing_id  BIGINT UNSIGNED NOT NULL,
    author_id   BIGINT UNSIGNED NOT NULL,
    rating      TINYINT UNSIGNED NOT NULL,
    comment     VARCHAR(2000) NOT NULL,
    host_reply  VARCHAR(2000) NULL,
    hidden_at   DATETIME NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_reviews_booking (booking_id),
    KEY idx_reviews_listing (listing_id, hidden_at, created_at),
    CONSTRAINT chk_review_rating CHECK (rating BETWEEN 1 AND 5),
    CONSTRAINT fk_reviews_booking FOREIGN KEY (booking_id) REFERENCES bookings(id),
    CONSTRAINT fk_reviews_listing FOREIGN KEY (listing_id) REFERENCES listings(id),
    CONSTRAINT fk_reviews_author FOREIGN KEY (author_id) REFERENCES users(id)
) ENGINE=InnoDB;

ALTER TABLE transactions
    ADD COLUMN refunded DECIMAL(12,2) NOT NULL DEFAULT 0 AFTER service_fee,
    ADD CONSTRAINT fk_tx_booking FOREIGN KEY (booking_id) REFERENCES bookings(id);

DELIMITER $$

-- Defence in depth: even a write that bypasses CreateBooking cannot double-book.
-- Two date ranges overlap when each starts before the other ends.
CREATE TRIGGER trg_bookings_bi BEFORE INSERT ON bookings
FOR EACH ROW
BEGIN
    IF NEW.status IN ('pending','confirmed') AND EXISTS (
        SELECT 1 FROM bookings b
        WHERE b.listing_id = NEW.listing_id
          AND (b.status = 'confirmed' OR (b.status = 'pending' AND b.hold_expires_at > NOW()))
          AND b.check_in < NEW.check_out AND b.check_out > NEW.check_in
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Those dates are no longer available.';
    END IF;
END$$

-- A review must belong to a completed stay by the same guest.
CREATE TRIGGER trg_reviews_bi BEFORE INSERT ON reviews
FOR EACH ROW
BEGIN
    DECLARE v_status VARCHAR(20);
    DECLARE v_guest BIGINT UNSIGNED;
    DECLARE v_listing BIGINT UNSIGNED;
    SELECT status, guest_id, listing_id INTO v_status, v_guest, v_listing FROM bookings WHERE id = NEW.booking_id;
    IF v_status <> 'completed' OR v_guest <> NEW.author_id THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'You can review a stay after it is completed.';
    END IF;
    SET NEW.listing_id = v_listing;
END$$

-- Keep the denormalised rating in listing_stats exact (hidden reviews excluded).
CREATE TRIGGER trg_reviews_ai AFTER INSERT ON reviews
FOR EACH ROW
BEGIN
    UPDATE listing_stats s
    JOIN (SELECT COUNT(*) AS n, AVG(rating) AS avg_r FROM reviews
          WHERE listing_id = NEW.listing_id AND hidden_at IS NULL) r
    SET s.review_count = r.n, s.rating_avg = r.avg_r
    WHERE s.listing_id = NEW.listing_id;
END$$

CREATE TRIGGER trg_reviews_au AFTER UPDATE ON reviews
FOR EACH ROW
BEGIN
    IF NOT (NEW.hidden_at <=> OLD.hidden_at) OR NEW.rating <> OLD.rating THEN
        UPDATE listing_stats s
        JOIN (SELECT COUNT(*) AS n, AVG(rating) AS avg_r FROM reviews
              WHERE listing_id = NEW.listing_id AND hidden_at IS NULL) r
        SET s.review_count = r.n, s.rating_avg = r.avg_r
        WHERE s.listing_id = NEW.listing_id;
    END IF;
END$$

DELIMITER ;
