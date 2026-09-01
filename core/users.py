"""User system for Think Box AI.

Auth, profiles, and API key management.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from core.foundation.logging import get_logger

logger = get_logger(__name__)


@dataclass
class User:
    id: str
    username: str
    email: str
    api_key_hash: str = ""
    is_active: bool = True
    is_admin: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_login: str | None = None


class UserStore:
    def __init__(self, db_path: str = "data/users.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                api_key_hash TEXT,
                is_active INTEGER DEFAULT 1,
                is_admin INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                last_login TEXT
            )
        """)
        conn.commit()
        conn.close()

    def create(self, username: str, email: str, is_admin: bool = False) -> tuple[User, str]:
        """Create a new user. Returns (user, api_key)."""
        user_id = f"user_{secrets.token_hex(8)}"
        api_key = f"tb_{secrets.token_hex(32)}"
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        user = User(id=user_id, username=username, email=email, api_key_hash=api_key_hash, is_admin=is_admin)

        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?)",
            (user.id, user.username, user.email, user.api_key_hash, int(user.is_active), int(user.is_admin), user.created_at, user.last_login))
        conn.commit()
        conn.close()

        logger.info(f"User created: {username}")
        return user, api_key

    def authenticate(self, api_key: str) -> User | None:
        """Authenticate by API key."""
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("SELECT * FROM users WHERE api_key_hash=? AND is_active=1", (api_key_hash,)).fetchone()
        conn.close()
        if row:
            return User(id=row[0], username=row[1], email=row[2], api_key_hash=row[3], is_active=bool(row[4]), is_admin=bool(row[5]), created_at=row[6], last_login=row[7])
        return None

    def get(self, user_id: str) -> User | None:
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        conn.close()
        if row:
            return User(id=row[0], username=row[1], email=row[2], api_key_hash=row[3], is_active=bool(row[4]), is_admin=bool(row[5]), created_at=row[6], last_login=row[7])
        return None

    def list(self) -> list[User]:
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("SELECT * FROM users").fetchall()
        conn.close()
        return [User(id=r[0], username=r[1], email=r[2], api_key_hash=r[3], is_active=bool(r[4]), is_admin=bool(r[5]), created_at=r[6], last_login=r[7]) for r in rows]
