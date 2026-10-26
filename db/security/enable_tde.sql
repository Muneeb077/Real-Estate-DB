-- InnoDB data-at-rest encryption (TDE). Run as an administrator once a keyring
-- component is loaded (see docker/mysql: mysqld.my + component_keyring_file.cnf;
-- in production use a KMS-backed keyring such as component_keyring_aws or the
-- managed equivalent, e.g. RDS storage encryption with a KMS key).
--
-- Each tablespace gets its own key, wrapped by the master key in the keyring.
-- Pages are encrypted on write and decrypted on read, so SQL and indexes work
-- unchanged while the .ibd files, redo/undo logs and binlogs are unreadable on disk.

-- refuse to run without a working keyring (otherwise ENCRYPTION='Y' fails half way)
DROP PROCEDURE IF EXISTS homenest.tmp_require_keyring;
DELIMITER $$
CREATE PROCEDURE homenest.tmp_require_keyring()
BEGIN
    IF NOT EXISTS (SELECT 1 FROM performance_schema.keyring_component_status
                    WHERE STATUS_KEY = 'Component_status' AND STATUS_VALUE = 'Active') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'No active keyring component: TDE not enabled.';
    END IF;
END$$
DELIMITER ;
CALL homenest.tmp_require_keyring();
DROP PROCEDURE homenest.tmp_require_keyring;

SET PERSIST default_table_encryption = ON;
SET PERSIST table_encryption_privilege_check = ON;
SET PERSIST innodb_redo_log_encrypt = ON;
SET PERSIST innodb_undo_log_encrypt = ON;
SET PERSIST binlog_encryption = ON;

ALTER SCHEMA homenest DEFAULT ENCRYPTION = 'Y';

-- encrypt tables created before TDE was switched on
DROP PROCEDURE IF EXISTS homenest.tmp_encrypt_all;

DELIMITER $$
CREATE PROCEDURE homenest.tmp_encrypt_all()
BEGIN
    DECLARE done INT DEFAULT 0;
    DECLARE t VARCHAR(64);
    DECLARE cur CURSOR FOR
        SELECT TABLE_NAME FROM information_schema.TABLES
         WHERE TABLE_SCHEMA = 'homenest' AND TABLE_TYPE = 'BASE TABLE'
           AND (CREATE_OPTIONS NOT LIKE '%ENCRYPTION="Y"%' OR CREATE_OPTIONS IS NULL);
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;
    OPEN cur;
    l: LOOP
        FETCH cur INTO t;
        IF done THEN LEAVE l; END IF;
        SET @ddl = CONCAT('ALTER TABLE homenest.`', t, '` ENCRYPTION = ''Y''');
        PREPARE s FROM @ddl;
        EXECUTE s;
        DEALLOCATE PREPARE s;
    END LOOP;
    CLOSE cur;
END$$
DELIMITER ;

CALL homenest.tmp_encrypt_all();
DROP PROCEDURE homenest.tmp_encrypt_all;

-- new master key; tablespace keys are re-wrapped, data is not rewritten
ALTER INSTANCE ROTATE INNODB MASTER KEY;

SELECT NAME, ENCRYPTION FROM information_schema.INNODB_TABLESPACES WHERE NAME LIKE 'homenest/%' ORDER BY NAME;
