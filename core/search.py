"""Full-text search system for Think Box AI.

SQLite FTS5 for jobs, findings, and memory.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path("data/search.db")


class SearchEngine:
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_fts()

    def _init_fts(self):
        """Initialize FTS5 virtual tables."""
        self.conn.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS jobs_fts USING fts5(
                job_id, intent, state, content, tokenize='porter unicode61'
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS findings_fts USING fts5(
                name, content, tokenize='porter unicode61'
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                key, value, layer, tokenize='porter unicode61'
            );
        """)
        self.conn.commit()

    def index_job(self, job_id: str, intent: str, state: str, content: str = ""):
        """Index a job for search."""
        self.conn.execute("INSERT INTO jobs_fts VALUES (?,?,?,?)", (job_id, intent, state, content))
        self.conn.commit()

    def index_finding(self, name: str, content: str):
        """Index a finding for search."""
        self.conn.execute("INSERT INTO findings_fts VALUES (?,?)", (name, content))
        self.conn.commit()

    def index_memory(self, key: str, value: str, layer: str):
        """Index a memory entry for search."""
        self.conn.execute("INSERT INTO memory_fts VALUES (?,?,?)", (key, value, layer))
        self.conn.commit()

    def search(self, query: str, limit: int = 20) -> dict[str, list[dict]]:
        """Search across all indexed content."""
        # Escape FTS5 special characters
        query = query.replace('"', '""')

        jobs = []
        try:
            rows = self.conn.execute(
                "SELECT job_id, intent, state, snippet(jobs_fts, 3, '[', ']', '...', 40) as snip FROM jobs_fts WHERE jobs_fts MATCH ? ORDER BY rank LIMIT ?",
                (query, limit)
            ).fetchall()
            jobs = [{"id": r[0], "intent": r[1], "state": r[2], "snippet": r[3]} for r in rows]
        except Exception:
            pass

        findings = []
        try:
            rows = self.conn.execute(
                "SELECT name, snippet(findings_fts, 1, '[', ']', '...', 40) as snip FROM findings_fts WHERE findings_fts MATCH ? ORDER BY rank LIMIT ?",
                (query, limit)
            ).fetchall()
            findings = [{"name": r[0], "snippet": r[1]} for r in rows]
        except Exception:
            pass

        memory = []
        try:
            rows = self.conn.execute(
                "SELECT key, value, layer FROM memory_fts WHERE memory_fts MATCH ? ORDER BY rank LIMIT ?",
                (query, limit)
            ).fetchall()
            memory = [{"key": r[0], "value": r[1], "layer": r[2]} for r in rows]
        except Exception:
            pass

        return {"jobs": jobs, "findings": findings, "memory": memory}

    def rebuild_index(self):
        """Rebuild all FTS indexes from source data."""
        # Clear existing
        self.conn.execute("DELETE FROM jobs_fts")
        self.conn.execute("DELETE FROM findings_fts")
        self.conn.execute("DELETE FROM memory_fts")

        # Index jobs
        jobs_dir = Path("jobs")
        if jobs_dir.exists():
            for state_dir in ["queue", "active", "done", "blocked"]:
                d = jobs_dir / state_dir
                if d.exists():
                    for jf in d.glob("job_*.json"):
                        import json
                        job = json.loads(jf.read_text())
                        self.index_job(job["id"], job.get("intent", ""), state_dir, json.dumps(job.get("inputs", {})))

        # Index findings
        findings_dir = Path("data/findings")
        if findings_dir.exists():
            for f in findings_dir.glob("*.md"):
                self.index_finding(f.stem, f.read_text()[:1000])

        # Index memory
        memory_db = Path("data/thinkbox_memory.db")
        if memory_db.exists():
            import sqlite3 as sq
            mconn = sq.connect(str(memory_db))
            for row in mconn.execute("SELECT key, value, layer FROM memory_entries").fetchall():
                self.index_memory(row[0], row[1], row[2])
            mconn.close()

        self.conn.commit()
        print("Search index rebuilt")


# Global instance
search = SearchEngine()
