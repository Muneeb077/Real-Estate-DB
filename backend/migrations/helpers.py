from alembic import op

from app.sqlrunner import run_file


def _exec(stmt):
    # exec_driver_sql skips SQLAlchemy's :bind parsing, so SQL text is sent verbatim.
    op.get_bind().exec_driver_sql(stmt)


def run_sql(*paths):
    for path in paths:
        run_file(_exec, path)


def drop(*statements):
    for stmt in statements:
        _exec(stmt)
