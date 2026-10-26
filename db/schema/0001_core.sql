-- =====================================================================
-- 0001 core: identities, hosts, addresses, listings
-- MySQL 8.0+ (InnoDB, utf8mb4). Encrypted columns hold AES-256-GCM
-- envelope ciphertext produced by the application (see backend/app/security/crypto.py);
-- *_hash columns hold HMAC-SHA256 blind indexes for equality lookups.
-- =====================================================================

CREATE TABLE users (
    id                  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    public_id           CHAR(26)        NOT NULL,
    email_enc           VARBINARY(512)  NOT NULL,
    email_hash          BINARY(32)      NOT NULL,
    email_verified_at   DATETIME        NULL,
    password_hash       VARCHAR(255)    NOT NULL,
    status              ENUM('active','suspended','deleted') NOT NULL DEFAULT 'active',
    mfa_secret_enc      VARBINARY(512)  NULL,
    mfa_enabled_at      DATETIME        NULL,
    mfa_last_step       BIGINT          NULL,
    mfa_recovery_hashes JSON            NULL,
    created_at          DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at          DATETIME(3)     NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    deleted_at          DATETIME        NULL,
    UNIQUE KEY uq_users_public_id (public_id),
    UNIQUE KEY uq_users_email_hash (email_hash)
) ENGINE=InnoDB;

-- A user can hold several roles (a guest who also hosts, an admin who also books).
CREATE TABLE user_roles (
    user_id     BIGINT UNSIGNED NOT NULL,
    role        ENUM('guest','host','admin') NOT NULL,
    granted_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, role),
    KEY idx_user_roles_role (role),
    CONSTRAINT fk_user_roles_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE user_profiles (
    user_id      BIGINT UNSIGNED PRIMARY KEY,
    display_name VARCHAR(120) NOT NULL,
    avatar_url   VARCHAR(500) NULL,
    bio          VARCHAR(1000) NULL,
    phone_enc    VARBINARY(512) NULL,
    phone_hash   BINARY(32) NULL,
    languages    JSON NULL,
    UNIQUE KEY uq_profiles_phone_hash (phone_hash),
    CONSTRAINT fk_profiles_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Replaces the old Agent table. legacy_agent_id keeps the old 2024xx ids traceable.
CREATE TABLE host_profiles (
    user_id             BIGINT UNSIGNED PRIMARY KEY,
    agency_name         VARCHAR(150) NULL,
    license_enc         VARBINARY(512) NULL,
    payout_enc          VARBINARY(1024) NULL,
    verification_status ENUM('unverified','pending','verified','rejected') NOT NULL DEFAULT 'unverified',
    verified_at         DATETIME NULL,
    commission_rate     DECIMAL(5,4) NOT NULL DEFAULT 0.0500,
    legacy_agent_id     INT NULL,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_host_legacy (legacy_agent_id),
    KEY idx_host_verification (verification_status),
    CONSTRAINT chk_host_commission CHECK (commission_rate BETWEEN 0 AND 0.2),
    CONSTRAINT fk_host_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Exact street is encrypted. City/state/country stay plain for search;
-- the public API only ever returns rounded coordinates.
-- SRID 4326 uses latitude-longitude axis order in MySQL.
CREATE TABLE addresses (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    street_enc  VARBINARY(1024) NULL,
    city        VARCHAR(80)  NOT NULL,
    state       VARCHAR(80)  NULL,
    postal_code VARCHAR(16)  NULL,
    country     CHAR(2)      NOT NULL,
    location    POINT        NOT NULL SRID 4326,
    SPATIAL INDEX sp_addresses_location (location),
    KEY idx_addresses_city (country, city)
) ENGINE=InnoDB;

CREATE TABLE listings (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    public_id       CHAR(26) NOT NULL,
    host_id         BIGINT UNSIGNED NOT NULL,
    address_id      BIGINT UNSIGNED NOT NULL,
    title           VARCHAR(140) NOT NULL,
    description     TEXT NOT NULL,
    listing_mode    ENUM('sale','long_term_rent','short_term_stay') NOT NULL,
    property_type   ENUM('house','apartment','condo','townhouse','villa','cabin','studio','loft') NOT NULL,
    bedrooms        TINYINT UNSIGNED NOT NULL DEFAULT 0,
    bathrooms       DECIMAL(3,1) NOT NULL DEFAULT 1.0,
    max_guests      TINYINT UNSIGNED NULL,
    size_sqft       INT UNSIGNED NULL,
    price           DECIMAL(12,2) NOT NULL,
    currency        CHAR(3) NOT NULL DEFAULT 'USD',
    price_unit      ENUM('total','month','night') NOT NULL,
    -- denormalised from addresses by trigger so the composite search index can include it
    city            VARCHAR(80) NOT NULL DEFAULT '',
    status          ENUM('draft','pending_review','published','paused','rejected','sold','rented','archived')
                    NOT NULL DEFAULT 'draft',
    moderation_note VARCHAR(500) NULL,
    version         INT UNSIGNED NOT NULL DEFAULT 1,
    legacy_p_id     INT NULL,
    published_at    DATETIME NULL,
    created_at      DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at      DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    deleted_at      DATETIME NULL,
    UNIQUE KEY uq_listings_public_id (public_id),
    UNIQUE KEY uq_listings_legacy (legacy_p_id),
    KEY idx_listings_search (status, listing_mode, city, price),
    KEY idx_listings_newest (status, published_at, id),
    KEY idx_listings_price (status, price, id),
    KEY idx_listings_host (host_id, status),
    FULLTEXT KEY ft_listings_text (title, description),
    CONSTRAINT chk_listing_price CHECK (price > 0),
    CONSTRAINT chk_listing_unit CHECK (
        (listing_mode = 'sale' AND price_unit = 'total') OR
        (listing_mode = 'long_term_rent' AND price_unit = 'month') OR
        (listing_mode = 'short_term_stay' AND price_unit = 'night')),
    CONSTRAINT chk_listing_guests CHECK (listing_mode <> 'short_term_stay' OR max_guests >= 1),
    CONSTRAINT fk_listings_host FOREIGN KEY (host_id) REFERENCES users(id),
    CONSTRAINT fk_listings_address FOREIGN KEY (address_id) REFERENCES addresses(id)
) ENGINE=InnoDB;

CREATE TABLE listing_photos (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    listing_id  BIGINT UNSIGNED NOT NULL,
    url         VARCHAR(500) NOT NULL,
    thumb_url   VARCHAR(500) NULL,
    alt         VARCHAR(200) NULL,
    sort_order  SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_photos_listing (listing_id, sort_order),
    CONSTRAINT fk_photos_listing FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE amenities (
    id        SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    code      VARCHAR(40) NOT NULL,
    label     VARCHAR(80) NOT NULL,
    category  ENUM('essentials','features','safety','outdoor','parking') NOT NULL,
    UNIQUE KEY uq_amenities_code (code)
) ENGINE=InnoDB;

CREATE TABLE listing_amenities (
    listing_id  BIGINT UNSIGNED NOT NULL,
    amenity_id  SMALLINT UNSIGNED NOT NULL,
    PRIMARY KEY (listing_id, amenity_id),
    KEY idx_la_amenity (amenity_id, listing_id),
    CONSTRAINT fk_la_listing FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE,
    CONSTRAINT fk_la_amenity FOREIGN KEY (amenity_id) REFERENCES amenities(id)
) ENGINE=InnoDB;

-- Counters kept off the hot listings row to avoid lock contention on views/favourites.
CREATE TABLE listing_stats (
    listing_id    BIGINT UNSIGNED PRIMARY KEY,
    views         INT UNSIGNED NOT NULL DEFAULT 0,
    favorites     INT UNSIGNED NOT NULL DEFAULT 0,
    review_count  INT UNSIGNED NOT NULL DEFAULT 0,
    rating_avg    DECIMAL(3,2) NULL,
    KEY idx_stats_rating (rating_avg),
    CONSTRAINT fk_stats_listing FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Platform settings editable by admins (commission, service fee, feature flags).
CREATE TABLE settings (
    k           VARCHAR(64) PRIMARY KEY,
    v           JSON NOT NULL,
    updated_by  BIGINT UNSIGNED NULL,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Append-only audit trail, filled by triggers (actor from the @actor_id session variable)
-- and by the API for admin actions.
CREATE TABLE audit_log (
    id          BIGINT UNSIGNED AUTO_INCREMENT,
    actor_id    BIGINT UNSIGNED NULL,
    action      VARCHAR(64) NOT NULL,
    entity      VARCHAR(64) NOT NULL,
    entity_id   BIGINT UNSIGNED NULL,
    old_data    JSON NULL,
    new_data    JSON NULL,
    ip          VARCHAR(45) NULL,
    created_at  DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (id),
    KEY idx_audit_entity (entity, entity_id),
    KEY idx_audit_actor (actor_id, created_at),
    KEY idx_audit_created (created_at)
) ENGINE=InnoDB;

DELIMITER $$

CREATE TRIGGER trg_listings_bi BEFORE INSERT ON listings
FOR EACH ROW
BEGIN
    SET NEW.city = (SELECT city FROM addresses WHERE id = NEW.address_id);
    IF NEW.status = 'published' AND NEW.published_at IS NULL THEN
        SET NEW.published_at = NOW();
    END IF;
END$$

CREATE TRIGGER trg_listings_bu BEFORE UPDATE ON listings
FOR EACH ROW
BEGIN
    IF NEW.address_id <> OLD.address_id THEN
        SET NEW.city = (SELECT city FROM addresses WHERE id = NEW.address_id);
    END IF;
    IF NEW.status = 'published' AND OLD.status <> 'published' THEN
        SET NEW.published_at = NOW();
    END IF;
    -- optimistic locking: every edit bumps the version the client must send back
    SET NEW.version = OLD.version + 1;
END$$

CREATE TRIGGER trg_listings_ai AFTER INSERT ON listings
FOR EACH ROW
BEGIN
    INSERT INTO listing_stats (listing_id) VALUES (NEW.id);
END$$

CREATE TRIGGER trg_addresses_au AFTER UPDATE ON addresses
FOR EACH ROW
BEGIN
    IF NEW.city <> OLD.city THEN
        UPDATE listings SET city = NEW.city WHERE address_id = NEW.id;
    END IF;
END$$

DELIMITER ;

INSERT INTO amenities (code, label, category) VALUES
 ('wifi','Wi-Fi','essentials'), ('kitchen','Kitchen','essentials'), ('washer','Washer','essentials'),
 ('dryer','Dryer','essentials'), ('ac','Air conditioning','essentials'), ('heating','Heating','essentials'),
 ('workspace','Dedicated workspace','features'), ('tv','TV','features'), ('fireplace','Fireplace','features'),
 ('gym','Gym','features'), ('elevator','Elevator','features'), ('pets','Pets allowed','features'),
 ('pool','Pool','outdoor'), ('hot_tub','Hot tub','outdoor'), ('garden','Garden','outdoor'),
 ('balcony','Balcony','outdoor'), ('bbq','BBQ grill','outdoor'), ('parking','Free parking','parking'),
 ('ev_charger','EV charger','parking'), ('garage','Garage','parking'), ('smoke_alarm','Smoke alarm','safety'),
 ('co_alarm','Carbon monoxide alarm','safety'), ('first_aid','First aid kit','safety'),
 ('security','24/7 security','safety');

INSERT INTO settings (k, v) VALUES
 ('service_fee_rate', '0.10'),
 ('default_commission_rate', '0.05'),
 ('booking_hold_minutes', '30'),
 ('new_listings_require_review', 'true');
