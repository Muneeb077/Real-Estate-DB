"""
Runs .sql files that use the mysql client's DELIMITER syntax, so the same files
work with both `mysql < file.sql` and the Alembic migrations.
"""
import os
import re

# repo layout: backend/app -> ../../db ; container layout: /app/app -> /db
DB_DIR = os.environ.get("DB_SQL_DIR") or os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "db"))


def split_statements(sql):
    statements, buf, delimiter = [], [], ";"
    for line in sql.splitlines():
        stripped = line.strip()
        m = re.match(r"(?i)^DELIMITER\s+(\S+)\s*$", stripped)
        if m:
            delimiter = m.group(1)
            continue
        if not buf and (not stripped or stripped.startswith("--")):
            continue
        buf.append(line)
        if stripped.endswith(delimiter):
            stmt = "\n".join(buf).rstrip()
            stmt = stmt[: -len(delimiter)].strip()
            if stmt:
                statements.append(stmt)
            buf = []
    tail = "\n".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def run_file(execute, relative_path):
    """
    `execute` is a callable taking one SQL string (e.g. alembic's op.execute).
    """
    with open(os.path.join(DB_DIR, relative_path)) as f:
        for stmt in split_statements(f.read()):
            execute(stmt)
