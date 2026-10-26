-- =====================================================================
-- 0006 scale: range-partition the append-only audit log by year.
-- Queries filtered by created_at touch only the matching partitions
-- (partition pruning), and retention is DROP PARTITION, a metadata
-- operation, instead of a huge DELETE (which the audit triggers forbid).
-- The partitioning column must be part of every unique key, hence the
-- composite primary key.
-- =====================================================================

ALTER TABLE audit_log
    DROP PRIMARY KEY,
    ADD PRIMARY KEY (id, created_at);

ALTER TABLE audit_log
    PARTITION BY RANGE COLUMNS (created_at) (
        PARTITION p2025 VALUES LESS THAN ('2026-01-01'),
        PARTITION p2026 VALUES LESS THAN ('2027-01-01'),
        PARTITION p2027 VALUES LESS THAN ('2028-01-01'),
        PARTITION pmax  VALUES LESS THAN (MAXVALUE)
    );
