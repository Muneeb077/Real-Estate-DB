-- Least-privilege accounts. Run as an administrator after real_estate.sql.
-- Replace the passwords before running; never use root from the application.
CREATE USER IF NOT EXISTS 'real_estate_app'@'%' IDENTIFIED BY 'change-me-app';
GRANT SELECT, INSERT, UPDATE ON real_estate.* TO 'real_estate_app'@'%';
GRANT EXECUTE ON real_estate.* TO 'real_estate_app'@'%';

CREATE USER IF NOT EXISTS 'real_estate_backup'@'localhost' IDENTIFIED BY 'change-me-backup';
GRANT SELECT, SHOW VIEW, TRIGGER, LOCK TABLES, EVENT ON real_estate.* TO 'real_estate_backup'@'localhost';
