import os
from contextlib import contextmanager

from mysql.connector import pooling

_pool = None


def _get_pool():
    """
    Lazily creates one connection pool per process. Credentials come from the
    environment (see .env.example) instead of being hard-coded.
    """
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="real_estate",
            pool_size=int(os.environ.get("DB_POOL_SIZE", 10)),
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", 3306)),
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            database=os.environ.get("DB_NAME", "real_estate"),
        )
    return _pool


@contextmanager
def get_connection():
    """
    Borrows a connection from the pool for the duration of a `with` block.
    Each request gets its own connection, so concurrent requests no longer
    overwrite a shared `self.connection`.
    """
    connection = _get_pool().get_connection()
    try:
        yield connection
    finally:
        connection.close()  # returns it to the pool
