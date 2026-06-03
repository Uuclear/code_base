"""SQLite connection and schema bootstrap for ReportDesk."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PACKAGE_ROOT / "data" / "reportdesk.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
SCHEMA_V2_PATH = Path(__file__).resolve().parent / "schema_v2.sql"


def default_db_path() -> Path:
    env = os.environ.get("REPORTDESK_DB")
    if env:
        return Path(env)
    return DEFAULT_DB_PATH


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _schema_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
        return int(row["v"] or 0) if row else 0
    except sqlite3.Error:
        return 0


def init_schema(conn: sqlite3.Connection) -> None:
    ddl = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(ddl)
    conn.commit()
    if _schema_version(conn) < 2 and SCHEMA_V2_PATH.is_file():
        conn.executescript(SCHEMA_V2_PATH.read_text(encoding="utf-8"))
        conn.commit()


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    conn = connect(db_path)
    init_schema(conn)
    return conn
