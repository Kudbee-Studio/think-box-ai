"""Database migration system for Think Box AI."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("data/thinkbox.db")

MIGRATIONS = [
    # v1: Initial schema
    """
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        intent TEXT NOT NULL,
        hat TEXT NOT NULL DEFAULT 'researcher',
        state TEXT NOT NULL DEFAULT 'queue',
        inputs TEXT DEFAULT '{}',
        plan TEXT DEFAULT '[]',
        execution TEXT DEFAULT '[]',
        artifacts TEXT DEFAULT '[]',
        evaluation TEXT DEFAULT '{}',
        cost TEXT DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """,
    # v2: Sessions
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        project_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        metadata TEXT DEFAULT '{}'
    );
    """,
    # v3: Messages
    """
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL REFERENCES sessions(id),
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        tool_name TEXT,
        tool_args TEXT,
        created_at TEXT NOT NULL
    );
    """,
    # v4: Memory
    """
    CREATE TABLE IF NOT EXISTS memory_entries (
        key TEXT PRIMARY KEY,
        layer TEXT NOT NULL,
        entry_type TEXT NOT NULL,
        value TEXT NOT NULL,
        agent_id TEXT DEFAULT '',
        task_id TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        metadata TEXT DEFAULT '{}',
        confidence REAL DEFAULT 1.0
    );
    """,
    # v5: Indexes
    "CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state);",
    "CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_hash);",
    "CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);",
    "CREATE INDEX IF NOT EXISTS idx_memory_layer ON memory_entries(layer);",
    "CREATE INDEX IF NOT EXISTS idx_memory_key ON memory_entries(key);",
]


def init_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Initialize database with all migrations."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # Track migrations
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
    """)

    # Apply pending migrations
    current = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] or 0
    for i, migration in enumerate(MIGRATIONS, 1):
        if i > current:
            conn.executescript(migration)
            conn.execute("INSERT INTO schema_migrations VALUES (?, ?)", (i, datetime.now(timezone.utc).isoformat()))
            print(f"Applied migration v{i}")

    conn.commit()
    return conn


def seed_db(conn: sqlite3.Connection):
    """Seed with initial data."""
    now = datetime.now(timezone.utc).isoformat()
    # Seed a sample job
    conn.execute("""
        INSERT OR IGNORE INTO jobs (id, intent, hat, state, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ("job_sample", "Sample job", "researcher", "done", now, now))
    conn.commit()


if __name__ == "__main__":
    conn = init_db()
    seed_db(conn)
    print(f"Database ready: {DB_PATH}")
    conn.close()
