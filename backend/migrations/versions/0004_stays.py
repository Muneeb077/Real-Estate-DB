"""short-term stays: pricing, bookings, payments, reviews; availability-aware search

Revision ID: 0004
Revises: 0003
"""
from migrations.helpers import run_sql, drop

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    run_sql("schema/0004_stays.sql", "procedures/stays.sql", "procedures/search_listings.sql", "events/stays.sql")


def downgrade():
    drop("DROP EVENT IF EXISTS ev_complete_stays", "DROP EVENT IF EXISTS ev_expire_booking_holds",
         "DROP PROCEDURE IF EXISTS CancelBooking", "DROP PROCEDURE IF EXISTS ConfirmBooking",
         "DROP PROCEDURE IF EXISTS CreateBooking", "DROP PROCEDURE IF EXISTS QuoteStay",
         "DROP FUNCTION IF EXISTS CalcStaySubtotal",
         "ALTER TABLE transactions DROP FOREIGN KEY fk_tx_booking, DROP COLUMN refunded",
         "DROP TABLE IF EXISTS reviews", "DROP TABLE IF EXISTS payments", "DROP TABLE IF EXISTS bookings",
         "DROP TABLE IF EXISTS price_rules", "DROP TABLE IF EXISTS blocked_dates")
