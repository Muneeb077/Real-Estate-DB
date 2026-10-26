-- Housekeeping with the MySQL event scheduler (event_scheduler=ON by default in 8.0+).
DROP EVENT IF EXISTS ev_purge_auth_data;

DELIMITER $$

CREATE EVENT ev_purge_auth_data
ON SCHEDULE EVERY 1 HOUR
COMMENT 'Delete expired one-time tokens, dead refresh tokens and old login attempts'
DO
BEGIN
    DELETE FROM auth_tokens WHERE expires_at < NOW() - INTERVAL 1 DAY;
    DELETE FROM refresh_tokens WHERE expires_at < NOW() - INTERVAL 1 DAY;
    DELETE FROM login_attempts WHERE created_at < NOW() - INTERVAL 30 DAY;
END$$

DELIMITER ;
