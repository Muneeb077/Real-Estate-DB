from alembic import op

from app.sqlrunner import run_file


def _exec(stmt):
    # exec_driver_sql skips SQLAlchemy's :bind parsing; PyMySQL still applies
    # %-formatting, so literal % (e.g. DATE_FORMAT '%Y-%m') is escaped.
    op.get_bind().exec_driver_sql(stmt.replace("%", "%%"))


def run_sql(*paths):
    for path in paths:
        run_file(_exec, path)


def drop(*statements):
    for stmt in statements:
        _exec(stmt)
