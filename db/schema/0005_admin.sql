-- =====================================================================
-- 0005 operations: tamper-resistant audit trail, backups registry.
-- =====================================================================

CREATE TABLE backups (
    id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    file_name    VARCHAR(200) NULL,
    size_bytes   BIGINT UNSIGNED NULL,
    sha256       CHAR(64) NULL,
    kek_id       VARCHAR(20) NULL,
    status       ENUM('running','succeeded','failed') NOT NULL DEFAULT 'running',
    error        VARCHAR(500) NULL,
    created_by   BIGINT UNSIGNED NULL,
    created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at  DATETIME NULL,
    KEY idx_backups_created (created_at)
) ENGINE=InnoDB;

DELIMITER $$

-- The audit log is append-only, even for the application's own DB user.
CREATE TRIGGER trg_audit_no_update BEFORE UPDATE ON audit_log
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'audit_log is append-only.';
END$$

CREATE TRIGGER trg_audit_no_delete BEFORE DELETE ON audit_log
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'audit_log is append-only.';
END$$

-- Audit triggers. The API sets @actor_id on every connection it uses (app/db.py),
-- so each row records who made the change, without trusting application code to
-- remember to log.

CREATE TRIGGER trg_audit_users_au AFTER UPDATE ON users
FOR EACH ROW
BEGIN
    IF NEW.status <> OLD.status OR NOT (NEW.mfa_enabled_at <=> OLD.mfa_enabled_at)
       OR NEW.password_hash <> OLD.password_hash OR NOT (NEW.email_verified_at <=> OLD.email_verified_at) THEN
        INSERT INTO audit_log (actor_id, action, entity, entity_id, old_data, new_data)
        VALUES (@actor_id, 'user.update', 'user', NEW.id,
                JSON_OBJECT('status', OLD.status, 'mfa', OLD.mfa_enabled_at IS NOT NULL,
                            'verified', OLD.email_verified_at IS NOT NULL),
                JSON_OBJECT('status', NEW.status, 'mfa', NEW.mfa_enabled_at IS NOT NULL,
                            'verified', NEW.email_verified_at IS NOT NULL,
                            'password_changed', NEW.password_hash <> OLD.password_hash));
    END IF;
END$$

CREATE TRIGGER trg_audit_roles_ai AFTER INSERT ON user_roles
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (actor_id, action, entity, entity_id, new_data)
    VALUES (@actor_id, 'role.grant', 'user', NEW.user_id, JSON_OBJECT('role', NEW.role));
END$$

CREATE TRIGGER trg_audit_roles_ad AFTER DELETE ON user_roles
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (actor_id, action, entity, entity_id, old_data)
    VALUES (@actor_id, 'role.revoke', 'user', OLD.user_id, JSON_OBJECT('role', OLD.role));
END$$

CREATE TRIGGER trg_audit_listings_au AFTER UPDATE ON listings
FOR EACH ROW
BEGIN
    IF NEW.status <> OLD.status OR NEW.price <> OLD.price OR NEW.title <> OLD.title THEN
        INSERT INTO audit_log (actor_id, action, entity, entity_id, old_data, new_data)
        VALUES (@actor_id, 'listing.update', 'listing', NEW.id,
                JSON_OBJECT('status', OLD.status, 'price', OLD.price, 'title', OLD.title),
                JSON_OBJECT('status', NEW.status, 'price', NEW.price, 'title', NEW.title,
                            'note', NEW.moderation_note));
    END IF;
END$$

CREATE TRIGGER trg_audit_hosts_au AFTER UPDATE ON host_profiles
FOR EACH ROW
BEGIN
    IF NEW.verification_status <> OLD.verification_status OR NEW.commission_rate <> OLD.commission_rate THEN
        INSERT INTO audit_log (actor_id, action, entity, entity_id, old_data, new_data)
        VALUES (@actor_id, 'host.update', 'user', NEW.user_id,
                JSON_OBJECT('verification', OLD.verification_status, 'commission', OLD.commission_rate),
                JSON_OBJECT('verification', NEW.verification_status, 'commission', NEW.commission_rate));
    END IF;
END$$

CREATE TRIGGER trg_audit_bookings_au AFTER UPDATE ON bookings
FOR EACH ROW
BEGIN
    IF NEW.status <> OLD.status THEN
        INSERT INTO audit_log (actor_id, action, entity, entity_id, old_data, new_data)
        VALUES (@actor_id, 'booking.status', 'booking', NEW.id,
                JSON_OBJECT('status', OLD.status),
                JSON_OBJECT('status', NEW.status, 'refund', NEW.refund_amount));
    END IF;
END$$

CREATE TRIGGER trg_audit_transactions_ai AFTER INSERT ON transactions
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (actor_id, action, entity, entity_id, new_data)
    VALUES (@actor_id, 'transaction.create', 'transaction', NEW.id,
            JSON_OBJECT('kind', NEW.kind, 'amount', NEW.amount, 'commission', NEW.commission,
                        'listing_id', NEW.listing_id));
END$$

CREATE TRIGGER trg_audit_settings_au AFTER UPDATE ON settings
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (actor_id, action, entity, old_data, new_data)
    VALUES (@actor_id, 'setting.update', 'setting',
            JSON_OBJECT('key', OLD.k, 'value', OLD.v), JSON_OBJECT('key', NEW.k, 'value', NEW.v));
END$$

CREATE TRIGGER trg_audit_reviews_au AFTER UPDATE ON reviews
FOR EACH ROW
BEGIN
    IF NOT (NEW.hidden_at <=> OLD.hidden_at) THEN
        INSERT INTO audit_log (actor_id, action, entity, entity_id, new_data)
        VALUES (@actor_id, IF(NEW.hidden_at IS NULL, 'review.unhide', 'review.hide'), 'review', NEW.id,
                JSON_OBJECT('listing_id', NEW.listing_id));
    END IF;
END$$

DELIMITER ;
