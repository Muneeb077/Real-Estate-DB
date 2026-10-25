-- Least-privilege accounts. Run once as an administrator, after replacing the passwords.
-- The application never connects as root.

CREATE DATABASE IF NOT EXISTS homenest CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- Schema changes (Alembic). Not used by the running app.
CREATE USER IF NOT EXISTS 'homenest_migrator'@'%' IDENTIFIED BY 'change-me' REQUIRE SSL;
GRANT ALL PRIVILEGES ON homenest.* TO 'homenest_migrator'@'%';
-- Creating triggers/routines with binary logging on and without SUPER needs
-- log_bin_trust_function_creators=1 on the server (RDS: set it in the parameter group).
SET PERSIST log_bin_trust_function_creators = 1;

-- The API: row-level DML and procedure execution only. No DROP/ALTER/CREATE, and no
-- DELETE on the audit trail or financial records.
CREATE USER IF NOT EXISTS 'homenest_app'@'%' IDENTIFIED BY 'change-me' REQUIRE SSL;
GRANT SELECT, INSERT, UPDATE, EXECUTE ON homenest.* TO 'homenest_app'@'%';
-- Table-level DELETE grants are in grants_after_migrate.sql (tables must exist first).

-- Read replica / analytics.
CREATE USER IF NOT EXISTS 'homenest_ro'@'%' IDENTIFIED BY 'change-me' REQUIRE SSL;
GRANT SELECT, EXECUTE ON homenest.* TO 'homenest_ro'@'%';

-- Backups: consistent dumps only.
CREATE USER IF NOT EXISTS 'homenest_backup'@'%' IDENTIFIED BY 'change-me' REQUIRE SSL;
GRANT SELECT, SHOW VIEW, TRIGGER, LOCK TABLES, EVENT, PROCESS ON *.* TO 'homenest_backup'@'%';
