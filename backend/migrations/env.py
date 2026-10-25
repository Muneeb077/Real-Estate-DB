"""
Migrations run as the `migrator` DB user (DDL rights), never as the app user.
Each revision executes the hand-written SQL files under /db.
"""
import os

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool

load_dotenv()

url = os.environ.get("MIGRATION_DATABASE_URL") or os.environ["DATABASE_URL"]


def _connect_args():
    if os.environ.get("DB_SSL_CA"):
        return {"ssl": {"ca": os.environ["DB_SSL_CA"]}}
    if os.environ.get("DB_SSL_REQUIRED", "").lower() == "true":
        return {"ssl": {"check_hostname": False, "verify_mode": 0}}
    return {}


def run_migrations_online():
    engine = create_engine(url, poolclass=pool.NullPool, connect_args=_connect_args())
    with engine.connect() as connection:
        context.configure(connection=connection, transactional_ddl=False)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    context.configure(url=url, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    run_migrations_online()
