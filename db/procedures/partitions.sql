DROP PROCEDURE IF EXISTS EnsureAuditPartition;
DROP PROCEDURE IF EXISTS DropAuditPartitionsBefore;
DROP EVENT IF EXISTS ev_audit_partitions;

DELIMITER $$

-- Splits next year out of pmax if it isn't there yet (idempotent).
CREATE PROCEDURE EnsureAuditPartition()
BEGIN
    DECLARE v_year INT DEFAULT YEAR(CURDATE()) + 1;
    IF NOT EXISTS (SELECT 1 FROM information_schema.PARTITIONS
                    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'audit_log'
                      AND PARTITION_NAME = CONCAT('p', v_year)) THEN
        SET @ddl = CONCAT('ALTER TABLE audit_log REORGANIZE PARTITION pmax INTO (',
                          'PARTITION p', v_year, ' VALUES LESS THAN (''', v_year + 1, '-01-01''), ',
                          'PARTITION pmax VALUES LESS THAN (MAXVALUE))');
        PREPARE stmt FROM @ddl;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END IF;
END$$

-- Retention: drops whole years older than p_year. Run deliberately by an operator.
CREATE PROCEDURE DropAuditPartitionsBefore(IN p_year INT)
BEGIN
    DECLARE done INT DEFAULT 0;
    DECLARE v_name VARCHAR(64);
    DECLARE cur CURSOR FOR
        SELECT PARTITION_NAME FROM information_schema.PARTITIONS
         WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'audit_log'
           AND PARTITION_NAME REGEXP '^p[0-9]{4}$' AND CAST(SUBSTRING(PARTITION_NAME, 2) AS UNSIGNED) < p_year;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET done = 1;
    OPEN cur;
    drop_loop: LOOP
        FETCH cur INTO v_name;
        IF done THEN LEAVE drop_loop; END IF;
        SET @ddl = CONCAT('ALTER TABLE audit_log DROP PARTITION ', v_name);
        PREPARE stmt FROM @ddl;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
    END LOOP;
    CLOSE cur;
END$$

CREATE EVENT ev_audit_partitions
ON SCHEDULE EVERY 1 MONTH STARTS CURRENT_TIMESTAMP
COMMENT 'Keep a partition ready for next year'
DO CALL EnsureAuditPartition()$$

DELIMITER ;
