-- =====================================================================
-- 0003 accounts & interactions: sessions, one-time tokens, lockout,
-- wishlists, saved searches, messaging, viewings, offers, transactions,
-- notifications, reports.
-- =====================================================================

-- Refresh tokens are stored only as SHA-256 hashes. family_id groups a chain
-- of rotations so reuse of an old token can revoke the whole chain.
CREATE TABLE refresh_tokens (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id     BIGINT UNSIGNED NOT NULL,
    family_id   CHAR(26) NOT NULL,
    token_hash  BINARY(32) NOT NULL,
    mfa         BOOLEAN NOT NULL DEFAULT FALSE,
    user_agent  VARCHAR(255) NULL,
    ip          VARCHAR(45) NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at  DATETIME NOT NULL,
    revoked_at  DATETIME NULL,
    UNIQUE KEY uq_refresh_hash (token_hash),
    KEY idx_refresh_family (family_id),
    KEY idx_refresh_user (user_id, revoked_at),
    CONSTRAINT fk_refresh_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Email verification and password reset links. Single use, short lived, hashed.
CREATE TABLE auth_tokens (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id     BIGINT UNSIGNED NOT NULL,
    purpose     ENUM('verify_email','reset_password') NOT NULL,
    token_hash  BINARY(32) NOT NULL,
    expires_at  DATETIME NOT NULL,
    used_at     DATETIME NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_auth_token_hash (token_hash),
    KEY idx_auth_tokens_user (user_id, purpose),
    CONSTRAINT fk_auth_tokens_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Failed logins keyed by the email blind index (works for unknown emails too,
-- without storing them) for account lockout.
CREATE TABLE login_attempts (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    email_hash  BINARY(32) NOT NULL,
    ip          VARCHAR(45) NULL,
    success     BOOLEAN NOT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_login_attempts (email_hash, created_at)
) ENGINE=InnoDB;

CREATE TABLE favorites (
    user_id     BIGINT UNSIGNED NOT NULL,
    listing_id  BIGINT UNSIGNED NOT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, listing_id),
    KEY idx_favorites_listing (listing_id),
    CONSTRAINT fk_fav_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_fav_listing FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE saved_searches (
    id               BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id          BIGINT UNSIGNED NOT NULL,
    name             VARCHAR(100) NOT NULL,
    query            JSON NOT NULL,
    alerts           BOOLEAN NOT NULL DEFAULT TRUE,
    last_notified_at DATETIME NULL,
    created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_saved_user (user_id),
    CONSTRAINT fk_saved_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- One conversation per (listing, guest). Message bodies are encrypted at rest.
CREATE TABLE conversations (
    id               BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    public_id        CHAR(26) NOT NULL,
    listing_id       BIGINT UNSIGNED NOT NULL,
    guest_id         BIGINT UNSIGNED NOT NULL,
    host_id          BIGINT UNSIGNED NOT NULL,
    last_message_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    guest_read_at    DATETIME NULL,
    host_read_at     DATETIME NULL,
    created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_conv_public (public_id),
    UNIQUE KEY uq_conv_listing_guest (listing_id, guest_id),
    KEY idx_conv_guest (guest_id, last_message_at),
    KEY idx_conv_host (host_id, last_message_at),
    CONSTRAINT fk_conv_listing FOREIGN KEY (listing_id) REFERENCES listings(id),
    CONSTRAINT fk_conv_guest FOREIGN KEY (guest_id) REFERENCES users(id),
    CONSTRAINT fk_conv_host FOREIGN KEY (host_id) REFERENCES users(id),
    CONSTRAINT chk_conv_parties CHECK (guest_id <> host_id)
) ENGINE=InnoDB;

CREATE TABLE messages (
    id               BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    conversation_id  BIGINT UNSIGNED NOT NULL,
    sender_id        BIGINT UNSIGNED NOT NULL,
    body_enc         VARBINARY(8192) NOT NULL,
    created_at       DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    KEY idx_messages_conv (conversation_id, id),
    CONSTRAINT fk_messages_conv FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    CONSTRAINT fk_messages_sender FOREIGN KEY (sender_id) REFERENCES users(id)
) ENGINE=InnoDB;

-- Viewing appointments for sale and long-term rental listings.
CREATE TABLE viewings (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    public_id     CHAR(26) NOT NULL,
    listing_id    BIGINT UNSIGNED NOT NULL,
    guest_id      BIGINT UNSIGNED NOT NULL,
    scheduled_at  DATETIME NOT NULL,
    note          VARCHAR(500) NULL,
    status        ENUM('requested','confirmed','declined','cancelled','completed') NOT NULL DEFAULT 'requested',
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_viewings_public (public_id),
    -- a guest can't double-book the same slot on the same listing
    UNIQUE KEY uq_viewings_slot (listing_id, guest_id, scheduled_at),
    KEY idx_viewings_guest (guest_id, scheduled_at),
    CONSTRAINT fk_viewings_listing FOREIGN KEY (listing_id) REFERENCES listings(id),
    CONSTRAINT fk_viewings_guest FOREIGN KEY (guest_id) REFERENCES users(id)
) ENGINE=InnoDB;

-- Purchase offers (sale) and rental applications (long-term rent).
CREATE TABLE offers (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    public_id     CHAR(26) NOT NULL,
    listing_id    BIGINT UNSIGNED NOT NULL,
    guest_id      BIGINT UNSIGNED NOT NULL,
    amount        DECIMAL(12,2) NOT NULL,
    move_in_date  DATE NULL,
    message       VARCHAR(1000) NULL,
    status        ENUM('pending','accepted','declined','withdrawn','superseded') NOT NULL DEFAULT 'pending',
    decided_at    DATETIME NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_offers_public (public_id),
    KEY idx_offers_listing (listing_id, status),
    KEY idx_offers_guest (guest_id, created_at),
    CONSTRAINT chk_offer_amount CHECK (amount > 0),
    CONSTRAINT fk_offers_listing FOREIGN KEY (listing_id) REFERENCES listings(id),
    CONSTRAINT fk_offers_guest FOREIGN KEY (guest_id) REFERENCES users(id)
) ENGINE=InnoDB;

-- Money that changed hands. One row per completed sale/rental (offer) or stay (booking, 0004).
-- Commission is computed only inside the procedures that insert here.
CREATE TABLE transactions (
    id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    kind         ENUM('sale','rental','stay') NOT NULL,
    listing_id   BIGINT UNSIGNED NOT NULL,
    host_id      BIGINT UNSIGNED NOT NULL,
    guest_id     BIGINT UNSIGNED NOT NULL,
    offer_id     BIGINT UNSIGNED NULL,
    booking_id   BIGINT UNSIGNED NULL,
    amount       DECIMAL(12,2) NOT NULL,
    commission   DECIMAL(12,2) NOT NULL,
    service_fee  DECIMAL(12,2) NOT NULL DEFAULT 0,
    currency     CHAR(3) NOT NULL DEFAULT 'USD',
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_tx_offer (offer_id),
    UNIQUE KEY uq_tx_booking (booking_id),
    KEY idx_tx_host (host_id, created_at),
    KEY idx_tx_created (created_at),
    CONSTRAINT chk_tx_source CHECK ((offer_id IS NULL) <> (booking_id IS NULL)),
    CONSTRAINT chk_tx_amounts CHECK (amount > 0 AND commission >= 0 AND service_fee >= 0),
    CONSTRAINT fk_tx_listing FOREIGN KEY (listing_id) REFERENCES listings(id),
    CONSTRAINT fk_tx_host FOREIGN KEY (host_id) REFERENCES users(id),
    CONSTRAINT fk_tx_guest FOREIGN KEY (guest_id) REFERENCES users(id),
    CONSTRAINT fk_tx_offer FOREIGN KEY (offer_id) REFERENCES offers(id)
) ENGINE=InnoDB;

CREATE TABLE notifications (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id     BIGINT UNSIGNED NOT NULL,
    kind        VARCHAR(40) NOT NULL,
    title       VARCHAR(200) NOT NULL,
    link        VARCHAR(300) NULL,
    read_at     DATETIME NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    KEY idx_notifications_user (user_id, read_at, id),
    CONSTRAINT fk_notifications_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Flags raised by users on listings, users or reviews, worked by admins.
CREATE TABLE reports (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    reporter_id   BIGINT UNSIGNED NOT NULL,
    entity        ENUM('listing','user','review') NOT NULL,
    entity_id     BIGINT UNSIGNED NOT NULL,
    reason        ENUM('spam','scam','inaccurate','offensive','other') NOT NULL,
    details       VARCHAR(1000) NULL,
    status        ENUM('open','dismissed','actioned') NOT NULL DEFAULT 'open',
    resolved_by   BIGINT UNSIGNED NULL,
    resolved_at   DATETIME NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_reports_once (reporter_id, entity, entity_id),
    KEY idx_reports_status (status, created_at),
    CONSTRAINT fk_reports_reporter FOREIGN KEY (reporter_id) REFERENCES users(id)
) ENGINE=InnoDB;

DELIMITER $$

-- Keeps listing_stats.favorites in step with the favorites table.
CREATE TRIGGER trg_favorites_ai AFTER INSERT ON favorites
FOR EACH ROW
BEGIN
    UPDATE listing_stats SET favorites = favorites + 1 WHERE listing_id = NEW.listing_id;
END$$

CREATE TRIGGER trg_favorites_ad AFTER DELETE ON favorites
FOR EACH ROW
BEGIN
    UPDATE listing_stats SET favorites = GREATEST(favorites, 1) - 1 WHERE listing_id = OLD.listing_id;
END$$

DELIMITER ;
