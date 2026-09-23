"""KUDBEECLI Phase 2 — hermetic SQLite paths for identity and think-trace stores."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any

from thinkbox.cli_inspect import repo_root
from thinkbox.identity import AgentIdentity, IdentityLedger
from thinkbox.path_safe import display_path, resolve_under_roots
from thinkbox.thinktrace import ThinkTrace, ThinkTraceCapture

_DEFAULT_DB_DIR = repo_root() / "data" / "thinkboxmd" / "db"
_IDENTITY_DEFAULT = "identity_ledger.db"
_TRACE_DEFAULT = "think_trace.db"


def default_db_dir() -> Path:
    """Configurable CLI persistence directory."""
    explicit = os.environ.get("THINKBOX_CLI_DB_DIR", "").strip()
    return Path(explicit) if explicit else _DEFAULT_DB_DIR


def _resolve_db_path(raw: str) -> Path:
    return resolve_under_roots(raw, allow_temp_dir=True)


def resolve_identity_db_path(explicit: str | None = None) -> Path:
    """Resolve identity ledger SQLite path (file may not exist yet)."""
    if explicit:
        return _resolve_db_path(explicit)
    env = os.environ.get("THINKBOX_IDENTITY_LEDGER_PATH", "").strip()
    if env:
        return _resolve_db_path(env)
    return default_db_dir() / _IDENTITY_DEFAULT


def resolve_trace_db_path(explicit: str | None = None) -> Path:
    """Resolve think-trace SQLite path (file may not exist yet)."""
    if explicit:
        return _resolve_db_path(explicit)
    env = os.environ.get("THINKBOX_TRACE_DB_PATH", "").strip()
    if env:
        return _resolve_db_path(env)
    return default_db_dir() / _TRACE_DEFAULT


def persist_paths_report() -> dict[str, Any]:
    """Summary of configured persistence locations."""
    id_path = resolve_identity_db_path()
    tr_path = resolve_trace_db_path()
    return {
        "db_dir": str(default_db_dir()),
        "identity_path": str(id_path),
        "identity_exists": id_path.is_file(),
        "trace_path": str(tr_path),
        "trace_exists": tr_path.is_file(),
        "evidence_label": "verified",
    }


class SQLiteIdentityStore:
    """Durable agent identity rows (hermetic SQLite, stdlib only)."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS identities (
                    agent_id TEXT PRIMARY KEY,
                    capabilities_json TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    revoked INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def upsert(self, identity: AgentIdentity) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO identities (
                    agent_id, capabilities_json, policy_version,
                    metadata_json, created_at, revoked
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    capabilities_json=excluded.capabilities_json,
                    policy_version=excluded.policy_version,
                    metadata_json=excluded.metadata_json,
                    created_at=excluded.created_at,
                    revoked=excluded.revoked
                """,
                (
                    identity.agent_id,
                    json.dumps(sorted(identity.capabilities)),
                    identity.policy_version,
                    json.dumps(identity.metadata),
                    identity.created_at,
                    1 if identity.revoked else 0,
                ),
            )
            self._conn.commit()

    def list_rows(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT agent_id, capabilities_json, policy_version, revoked
                FROM identities
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, limit),),
            )
            rows: list[dict[str, Any]] = []
            for row in cur.fetchall():
                caps = json.loads(row["capabilities_json"])
                rows.append(
                    {
                        "agent_id": row["agent_id"],
                        "capabilities": caps,
                        "policy_version": row["policy_version"],
                        "revoked": bool(row["revoked"]),
                    }
                )
            return rows

    def count(self) -> int:
        with self._lock:
            cur = self._conn.execute("SELECT COUNT(*) AS n FROM identities")
            return int(cur.fetchone()["n"])


class SQLiteTraceStore:
    """Durable think-trace rows for CLI inspection."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS traces (
                    trace_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    thought TEXT NOT NULL,
                    grounded INTEGER NOT NULL,
                    evidence_json TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    captured_at TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def append(self, trace: ThinkTrace) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO traces (
                    trace_id, agent_id, thought, grounded, evidence_json,
                    confidence, captured_at, tags_json, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace.trace_id,
                    trace.agent_id,
                    trace.thought,
                    1 if trace.grounded else 0,
                    json.dumps(trace.evidence_refs),
                    trace.confidence,
                    trace.captured_at,
                    json.dumps(trace.tags),
                    json.dumps(trace.metadata),
                ),
            )
            self._conn.commit()

    def list_rows(self, limit: int = 50, grounded: bool | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if grounded is None:
                cur = self._conn.execute(
                    """
                    SELECT trace_id, agent_id, grounded, confidence, captured_at
                    FROM traces ORDER BY captured_at DESC LIMIT ?
                    """,
                    (max(1, limit),),
                )
            else:
                cur = self._conn.execute(
                    """
                    SELECT trace_id, agent_id, grounded, confidence, captured_at
                    FROM traces WHERE grounded = ?
                    ORDER BY captured_at DESC LIMIT ?
                    """,
                    (1 if grounded else 0, max(1, limit)),
                )
            return [dict(row) for row in cur.fetchall()]

    def stats(self) -> dict[str, int]:
        with self._lock:
            total = int(self._conn.execute("SELECT COUNT(*) FROM traces").fetchone()[0])
            grounded = int(
                self._conn.execute("SELECT COUNT(*) FROM traces WHERE grounded = 1").fetchone()[0]
            )
            return {"total": total, "grounded": grounded, "ungrounded": total - grounded}


def sync_identity_ledger_to_sqlite(ledger: IdentityLedger, path: Path) -> int:
    """Persist in-memory identities to SQLite; returns rows written."""
    store = SQLiteIdentityStore(path)
    try:
        rows = ledger.list()
        for row in rows:
            ident = AgentIdentity(
                agent_id=row["agent_id"],
                capabilities=set(row["capabilities"]),
                policy_version=row["policy_version"],
                revoked=row["revoked"],
            )
            store.upsert(ident)
        return len(rows)
    finally:
        store.close()


def sync_traces_to_sqlite(capture: ThinkTraceCapture, path: Path) -> int:
    """Persist in-memory traces to SQLite; returns rows written."""
    store = SQLiteTraceStore(path)
    try:
        traces = capture.list_recent(limit=10_000)
        for trace in traces:
            store.append(trace)
        return len(traces)
    finally:
        store.close()


def import_sample_identity(path: Path, agent_id: str = "cli_phase2_seed") -> None:
    """Hermetic seed row for empty stores (tests / persist init)."""
    ledger = IdentityLedger()
    ledger.register(agent_id=agent_id, capabilities=["cli:inspect"], policy_version="phase2")
    sync_identity_ledger_to_sqlite(ledger, path)


def init_persist_files(
    identity_path: Path | None = None,
    trace_path: Path | None = None,
    seed: bool = False,
) -> dict[str, Any]:
    """Create SQLite files and optional seed identity."""
    id_p = identity_path or resolve_identity_db_path()
    tr_p = trace_path or resolve_trace_db_path()
    id_store = SQLiteIdentityStore(id_p)
    tr_store = SQLiteTraceStore(tr_p)
    try:
        if seed:
            import_sample_identity(id_p)
        return {
            "identity_path": str(id_p),
            "trace_path": str(tr_p),
            "identity_count": id_store.count(),
            "trace_stats": tr_store.stats(),
            "seeded": seed,
        }
    finally:
        id_store.close()
        tr_store.close()
