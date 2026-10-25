"""public search: v_public_listings view and SearchListings procedure

Revision ID: 0002
Revises: 0001
"""
from migrations.helpers import run_sql, drop

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    run_sql("schema/0002_search.sql", "views/v_public_listings.sql", "procedures/search_listings.sql")


def downgrade():
    drop("DROP PROCEDURE IF EXISTS SearchListings", "DROP VIEW IF EXISTS v_public_listings",
         "DROP INDEX idx_listings_city_mode ON listings")
