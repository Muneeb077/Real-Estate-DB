"""scale: partition audit_log by year with automatic partition maintenance

Revision ID: 0006
Revises: 0005
"""
from migrations.helpers import run_sql, drop

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    run_sql("schema/0006_partitioning.sql", "procedures/partitions.sql")


def downgrade():
    drop("DROP EVENT IF EXISTS ev_audit_partitions", "DROP PROCEDURE IF EXISTS DropAuditPartitionsBefore",
         "DROP PROCEDURE IF EXISTS EnsureAuditPartition", "ALTER TABLE audit_log REMOVE PARTITIONING",
         "ALTER TABLE audit_log DROP PRIMARY KEY, ADD PRIMARY KEY (id)")
