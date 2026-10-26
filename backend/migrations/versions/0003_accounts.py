"""accounts and interactions: sessions, tokens, wishlists, messaging, offers

Revision ID: 0003
Revises: 0002
"""
from migrations.helpers import run_sql, drop

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    run_sql("schema/0003_accounts.sql", "procedures/accept_offer.sql", "events/purge_tokens.sql")


def downgrade():
    drop("DROP EVENT IF EXISTS ev_purge_auth_data", "DROP PROCEDURE IF EXISTS AcceptOffer",
         *[f"DROP TABLE IF EXISTS {t}" for t in (
             "reports", "notifications", "transactions", "offers", "viewings", "messages", "conversations",
             "saved_searches", "favorites", "login_attempts", "auth_tokens", "refresh_tokens")])
