"""core schema: users, roles, hosts, addresses, listings

Revision ID: 0001
Revises:
"""
from migrations.helpers import run_sql, drop

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    run_sql("schema/0001_core.sql")


def downgrade():
    drop(
        "DROP TABLE IF EXISTS audit_log", "DROP TABLE IF EXISTS settings", "DROP TABLE IF EXISTS listing_stats",
        "DROP TABLE IF EXISTS listing_amenities", "DROP TABLE IF EXISTS amenities",
        "DROP TABLE IF EXISTS listing_photos", "DROP TABLE IF EXISTS listings", "DROP TABLE IF EXISTS addresses",
        "DROP TABLE IF EXISTS host_profiles", "DROP TABLE IF EXISTS user_profiles",
        "DROP TABLE IF EXISTS user_roles", "DROP TABLE IF EXISTS users",
    )
