-- =====================================================================
-- 0007 remove two-factor authentication: drop the TOTP columns and the
-- per-session MFA flag, and stop auditing a column that no longer exists.
-- =====================================================================

DROP TRIGGER IF EXISTS trg_audit_users_au;

ALTER TABLE users
    DROP COLUMN mfa_secret_enc,
    DROP COLUMN mfa_enabled_at,
    DROP COLUMN mfa_last_step,
    DROP COLUMN mfa_recovery_hashes;

ALTER TABLE refresh_tokens DROP COLUMN mfa;

DELIMITER $$

CREATE TRIGGER trg_audit_users_au AFTER UPDATE ON users
FOR EACH ROW
BEGIN
    IF NEW.status <> OLD.status
       OR NEW.password_hash <> OLD.password_hash OR NOT (NEW.email_verified_at <=> OLD.email_verified_at) THEN
        INSERT INTO audit_log (actor_id, action, entity, entity_id, old_data, new_data)
        VALUES (@actor_id, 'user.update', 'user', NEW.id,
                JSON_OBJECT('status', OLD.status, 'verified', OLD.email_verified_at IS NOT NULL),
                JSON_OBJECT('status', NEW.status, 'verified', NEW.email_verified_at IS NOT NULL,
                            'password_changed', NEW.password_hash <> OLD.password_hash));
    END IF;
END$$

DELIMITER ;
