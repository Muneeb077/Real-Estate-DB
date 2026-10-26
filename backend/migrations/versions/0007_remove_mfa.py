"""remove two-factor authentication columns

Revision ID: 0007
Revises: 0006
"""
from migrations.helpers import run_sql, drop

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    run_sql("schema/0007_remove_mfa.sql")


def downgrade():
    drop("DROP TRIGGER IF EXISTS trg_audit_users_au",
         """ALTER TABLE users
                ADD COLUMN mfa_secret_enc VARBINARY(512) NULL,
                ADD COLUMN mfa_enabled_at DATETIME NULL,
                ADD COLUMN mfa_last_step BIGINT NULL,
                ADD COLUMN mfa_recovery_hashes JSON NULL""",
         "ALTER TABLE refresh_tokens ADD COLUMN mfa BOOLEAN NOT NULL DEFAULT FALSE AFTER token_hash",
         """CREATE TRIGGER trg_audit_users_au AFTER UPDATE ON users
            FOR EACH ROW
            BEGIN
                IF NEW.status <> OLD.status OR NOT (NEW.mfa_enabled_at <=> OLD.mfa_enabled_at)
                   OR NEW.password_hash <> OLD.password_hash OR NOT (NEW.email_verified_at <=> OLD.email_verified_at) THEN
                    INSERT INTO audit_log (actor_id, action, entity, entity_id, old_data, new_data)
                    VALUES (@actor_id, 'user.update', 'user', NEW.id,
                            JSON_OBJECT('status', OLD.status, 'mfa', OLD.mfa_enabled_at IS NOT NULL,
                                        'verified', OLD.email_verified_at IS NOT NULL),
                            JSON_OBJECT('status', NEW.status, 'mfa', NEW.mfa_enabled_at IS NOT NULL,
                                        'verified', NEW.email_verified_at IS NOT NULL,
                                        'password_changed', NEW.password_hash <> OLD.password_hash));
                END IF;
            END""")
