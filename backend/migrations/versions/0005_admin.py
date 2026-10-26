"""operations: audit triggers, append-only audit log, backups, analytics procedures

Revision ID: 0005
Revises: 0004
"""
from migrations.helpers import run_sql, drop

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

TRIGGERS = ("trg_audit_no_update", "trg_audit_no_delete", "trg_audit_users_au", "trg_audit_roles_ai",
            "trg_audit_roles_ad", "trg_audit_listings_au", "trg_audit_hosts_au", "trg_audit_bookings_au",
            "trg_audit_transactions_ai", "trg_audit_settings_au", "trg_audit_reviews_au")
PROCEDURES = ("HostEarnings", "HostListingPerformance", "AdminKpis", "AdminMonthlyGmv", "AdminTopHosts",
              "AdminCityStats")


def upgrade():
    run_sql("schema/0005_admin.sql", "procedures/analytics.sql", "views/v_public_listings.sql")


def downgrade():
    drop(*[f"DROP PROCEDURE IF EXISTS {p}" for p in PROCEDURES],
         *[f"DROP TRIGGER IF EXISTS {t}" for t in TRIGGERS],
         "DROP TABLE IF EXISTS backups")
