"""KUDBEE — Memory Evolution Engine.

Storing 389 memories is not learning. Tracking what *happened* to each memory is:

  created -> provisional
  reinforced -> supported by a later independent run
  contradicted -> a later run disagreed
  corrected -> a contradicted memory replaced by a newer value
  promoted -> reached VERIFIED_KNOWLEDGE after surviving challenges
  decayed -> not re-seen for N sessions; confidence faded
  proven_useful -> actually retrieved and used by later work

Every transition is an append-only event, so memory becomes measurable learning
rather than a pile of rows.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB = "data/thinkboxmd/db/memory_evolution.db"

EVENTS = [
    "created", "reinforced", "contradicted", "corrected",
    "promoted", "decayed", "proven_useful",
]


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def memory_key(claim_id: str, content_hash: str) -> str:
    return f"mem_{claim_id}_{content_hash[:12]}"


def topic_hash(text: str) -> str:
    """Stable identity for a *concept*, so re-statements reinforce the same memory."""
    import re
    norm = re.sub(r"\s+", " ", (text or "").strip().lower())
    return hashlib.sha256(norm.encode()).hexdigest()[:16]


@dataclass
class MemoryState:
    memory_key: str
    topic_hash: str
    content: str
    state: str = "provisional"        # provisional|supported|promoted|contradicted|decayed
    confidence: float = 0.5
    created_session: str = ""
    last_session: str = ""
    seen_count: int = 0
    reinforce_count: int = 0
    contradict_count: int = 0
    corrections: int = 0
    useful_count: int = 0
    tier: str = ""
    claim_id: str = ""
    history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_key": self.memory_key,
            "topic_hash": self.topic_hash,
            "content": self.content,
            "state": self.state,
            "confidence": round(self.confidence, 4),
            "created_session": self.created_session,
            "last_session": self.last_session,
            "seen_count": self.seen_count,
            "reinforce_count": self.reinforce_count,
            "contradict_count": self.contradict_count,
            "corrections": self.corrections,
            "useful_count": self.useful_count,
            "tier": self.tier,
            "claim_id": self.claim_id,
            "history": self.history,
        }


class MemoryEvolution:
    """Append-only memory lifecycle tracker on SQLite."""

    def __init__(self, db_path: str | Path = DEFAULT_DB) -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    memory_key TEXT PRIMARY KEY,
                    topic_hash TEXT NOT NULL,
                    content TEXT NOT NULL,
                    state TEXT NOT NULL,
                    confidence REAL DEFAULT 0.5,
                    created_session TEXT, last_session TEXT,
                    seen_count INTEGER DEFAULT 0,
                    reinforce_count INTEGER DEFAULT 0,
                    contradict_count INTEGER DEFAULT 0,
                    corrections INTEGER DEFAULT 0,
                    useful_count INTEGER DEFAULT 0,
                    tier TEXT, claim_id TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_mem_topic ON memories(topic_hash);
                CREATE INDEX IF NOT EXISTS idx_mem_state ON memories(state);

                CREATE TABLE IF NOT EXISTS memory_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_key TEXT NOT NULL,
                    event TEXT NOT NULL,
                    from_state TEXT, to_state TEXT,
                    session_id TEXT, reason TEXT, created_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_me_key ON memory_events(memory_key);
                """
            )
            self._conn.commit()

    def _event(self, key: str, event: str, frm: str, to: str, session: str, reason: str) -> None:
        self._conn.execute(
            "INSERT INTO memory_events (memory_key, event, from_state, to_state, session_id, reason, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (key, event, frm, to, session, reason, _utc()),
        )

    # -- lifecycle ---------------------------------------------------------

    def observe(
        self,
        session_id: str,
        claim_id: str,
        content: str,
        tier: str,
        evidence_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        """Record one observation of a concept, updating its lifecycle state."""
        th = topic_hash(content)
        key = f"mem_{th}"
        with self._lock:
            row = self._conn.execute("SELECT * FROM memories WHERE memory_key=?", (key,)).fetchone()
            if row is None:
                state = "supported" if evidence_refs else "provisional"
                self._conn.execute(
                    "INSERT INTO memories (memory_key, topic_hash, content, state, confidence, "
                    "created_session, last_session, seen_count, tier, claim_id) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (key, th, content[:500], state, 0.5, session_id, session_id, 1, tier, claim_id),
                )
                self._event(key, "created", "", state, session_id, f"tier={tier}")
                self._conn.commit()
            else:
                frm = row["state"]
                reinforce = row["reinforce_count"]
                contradict = row["contradict_count"]
                seen = row["seen_count"]

                # same concept seen again: reinforce if it agrees in shape, else contradict
                if tier == row["tier"]:
                    reinforce += 1
                    to = "supported" if frm == "provisional" else frm
                    self._event(key, "reinforced", frm, to, session_id, f"repeat tier={tier}")
                    conf = min(0.95, (row["confidence"] or 0.5) + 0.08)
                else:
                    contradict += 1
                    to = "contradicted"
                    self._event(key, "contradicted", frm, to, session_id, f"{row['tier']}->{tier}")
                    conf = max(0.05, (row["confidence"] or 0.5) - 0.12)

                # promotion gate: repeatedly reinforced with evidence
                if reinforce >= 2 and evidence_refs and to != "contradicted":
                    self._event(key, "promoted", to, "promoted", session_id, f"reinforce={reinforce}")
                    to = "promoted"
                    conf = max(conf, 0.85)

                # a contradicted memory can be corrected by the newer observation
                if to == "contradicted" and tier in ("EVIDENCE", "INFERENCE"):
                    self._event(key, "corrected", "contradicted", "supported", session_id, f"new tier={tier}")
                    to = "supported"
                    conf = 0.6

                self._conn.execute(
                    "UPDATE memories SET state=?, confidence=?, last_session=?, seen_count=?, "
                    "reinforce_count=?, contradict_count=?, corrections=corrections+?, tier=?, content=? "
                    "WHERE memory_key=?",
                    (
                        to, conf, session_id, seen + 1, reinforce, contradict,
                        1 if to == "supported" and frm == "contradicted" else 0,
                        tier, content[:500], key,
                    ),
                )
                self._conn.commit()
        return self.get(key)

    def decay_stale(self, current_session: str, stale_after: int = 3) -> list[str]:
        """Fade memories not observed for N sessions; returns keys decayed."""
        decayed: list[str] = []
        with self._lock:
            rows = self._conn.execute(
                "SELECT memory_key, state, last_session FROM memories WHERE state IN ('provisional','supported')"
            ).fetchall()
            for r in rows:
                # session ids are time-ordered; compare by recency rank instead of parsing
                if r["last_session"] and r["last_session"] != current_session:
                    gap = self._session_gap(cur_session=r["last_session"], current=current_session)
                    if gap >= stale_after:
                        self._event(r["memory_key"], "decayed", r["state"], "decayed", current_session,
                                    f"unseen for {gap} sessions")
                        self._conn.execute(
                            "UPDATE memories SET state='decayed', confidence=MAX(0.05, confidence-0.2) "
                            "WHERE memory_key=?", (r["memory_key"],),
                        )
                        decayed.append(r["memory_key"])
            self._conn.commit()
        return decayed

    def _session_gap(self, cur_session: str, current: str) -> int:
        rows = [r["session_id"] for r in self._conn.execute(
            "SELECT DISTINCT session_id FROM memory_events ORDER BY session_id"
        ).fetchall()]
        if cur_session in rows and current in rows:
            return rows.index(current) - rows.index(cur_session)
        return 0

    def mark_useful(self, memory_key: str, session_id: str, reason: str = "") -> bool:
        with self._lock:
            row = self._conn.execute("SELECT state FROM memories WHERE memory_key=?", (memory_key,)).fetchone()
            if not row:
                return False
            self._event(memory_key, "proven_useful", row["state"], row["state"], session_id, reason)
            self._conn.execute(
                "UPDATE memories SET useful_count = useful_count + 1 WHERE memory_key=?", (memory_key,)
            )
            self._conn.commit()
        return True

    def get(self, memory_key: str) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM memories WHERE memory_key=?", (memory_key,)).fetchone()
            ev = self._conn.execute(
                "SELECT event, from_state, to_state, session_id, reason, created_at "
                "FROM memory_events WHERE memory_key=? ORDER BY id",
                (memory_key,),
            ).fetchall()
        if not row:
            return {}
        d = dict(row)
        d["history"] = [dict(e) for e in ev]
        return d

    def stats(self) -> dict[str, Any]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT state, COUNT(*) n FROM memories GROUP BY state"
            ).fetchall()
            ev = self._conn.execute(
                "SELECT event, COUNT(*) n FROM memory_events GROUP BY event"
            ).fetchall()
            totals = self._conn.execute(
                "SELECT SUM(reinforce_count) r, SUM(contradict_count) c, SUM(corrections) k, "
                "SUM(useful_count) u, COUNT(*) n FROM memories"
            ).fetchone()
        return {
            "by_state": {r["state"]: r["n"] for r in rows},
            "by_event": {r["event"]: r["n"] for r in ev},
            "reinforced": totals["r"] or 0,
            "contradicted": totals["c"] or 0,
            "corrected": totals["k"] or 0,
            "proven_useful": totals["u"] or 0,
            "total_memories": totals["n"] or 0,
        }
