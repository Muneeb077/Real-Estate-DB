"""
Database access. SQLAlchemy Core is used only for its connection pool and
parameter binding: queries are hand-written SQL so the database work (stored
procedures, views, window functions) stays visible.
"""
from contextlib import contextmanager
from decimal import Decimal
from datetime import date, datetime

from flask import current_app, g, has_request_context
from sqlalchemy import create_engine, text

_engines = {}


def _make_engine(url, cfg):
    connect_args = {}
    if cfg.get("DB_SSL_CA"):
        connect_args["ssl"] = {"ca": cfg["DB_SSL_CA"]}
    elif cfg.get("DB_SSL_REQUIRED"):
        # TLS without CA verification (e.g. MySQL's auto-generated certs in development)
        connect_args["ssl"] = {"check_hostname": False, "verify_mode": 0}
    return create_engine(
        url,
        pool_size=cfg.get("DB_POOL_SIZE", 10),
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args=connect_args,
    )


def init_app(app):
    cfg = app.config
    _engines[app] = {
        "primary": _make_engine(cfg["DATABASE_URL"], cfg),
        "replica": _make_engine(cfg["DATABASE_REPLICA_URL"], cfg) if cfg.get("DATABASE_REPLICA_URL") else None,
    }


def engine(read=False):
    engines = _engines[current_app._get_current_object()]
    if read and engines["replica"] is not None:
        return engines["replica"]
    return engines["primary"]


def _actor_id():
    if has_request_context():
        user = g.get("user")
        return user["id"] if user else None
    return None


def _prepare(conn):
    # Triggers read @actor_id to attribute changes in audit_log.
    conn.execute(text("SET @actor_id = :a"), {"a": _actor_id()})


@contextmanager
def transaction():
    """
    One connection, one DB transaction. Commits on success, rolls back on error.
    """
    with engine().begin() as conn:
        _prepare(conn)
        yield conn


def _row(r):
    return {k: _jsonable(v) for k, v in r._mapping.items()}


def _jsonable(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def query(sql, params=None, read=False, conn=None):
    if conn is not None:
        return [_row(r) for r in conn.execute(text(sql), params or {})]
    with engine(read).connect() as c:
        return [_row(r) for r in c.execute(text(sql), params or {})]


def one(sql, params=None, read=False, conn=None):
    rows = query(sql, params, read, conn)
    return rows[0] if rows else None


def scalar(sql, params=None, conn=None):
    if conn is not None:
        return conn.execute(text(sql), params or {}).scalar()
    with engine().connect() as c:
        return c.execute(text(sql), params or {}).scalar()


def execute(sql, params=None, conn=None):
    """
    Runs a write statement. Returns (rowcount, lastrowid).
    """
    if conn is not None:
        res = conn.execute(text(sql), params or {})
        return res.rowcount, res.lastrowid
    with transaction() as c:
        res = c.execute(text(sql), params or {})
        return res.rowcount, res.lastrowid


def call(procedure, args, read=False, conn=None):
    """
    Calls a stored procedure and returns its first result set as dicts.
    """
    placeholders = ", ".join(f":p{i}" for i in range(len(args)))
    params = {f"p{i}": v for i, v in enumerate(args)}
    sql = f"CALL {procedure}({placeholders})"

    def run(c):
        res = c.execute(text(sql), params)
        return [_row(r) for r in res] if res.returns_rows else []

    if conn is not None:
        return run(conn)
    if read:
        with engine(read=True).connect() as c:
            return run(c)
    with transaction() as c:
        return run(c)
