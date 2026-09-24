"""Shared SQLite connection defaults (foundation layer)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_BUSY_TIMEOUT_MS = 5000


def open_sqlite(
    db_path: str | Path,
    *,
    check_same_thread: bool = True,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    foreign_keys: bool = True,
) -> sqlite3.Connection:
    """Open SQLite with WAL, foreign keys, and bounded lock wait."""
    conn = sqlite3.connect(str(db_path), check_same_thread=check_same_thread)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(f"PRAGMA foreign_keys={'ON' if foreign_keys else 'OFF'}")
    conn.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
    return conn
