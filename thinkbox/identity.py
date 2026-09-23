"""KUDBEE Control Fabric — Agent identity ledger and capability scopes.

Durable authority is the first requirement of a control fabric: an agent
must know who it is, which capabilities it may exercise, and which policy
version it accepted before any side effect is permitted.

When db_path is provided, identities persist to SQLite and survive
process/session boundaries. Without db_path, the ledger is in-memory
only (backward compatible).
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class AgentIdentity:
    agent_id: str
    capabilities: set[str] = field(default_factory=set)
    policy_version: str = "0"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    revoked: bool = False

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


class IdentityLedger:
    """Registry of agent identities with immutable capability scopes.

    Persistence: when db_path is provided, identities are also written
    to SQLite. In-memory mode (default) preserves the original behavior.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._identities: dict[str, AgentIdentity] = {}
        self._lock = threading.Lock()
        self._db_path = str(db_path) if db_path else None
        self._conn = None
        if self._db_path:
            self._init_db()

    def _init_db(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_identities (
                agent_id TEXT PRIMARY KEY,
                capabilities TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                metadata TEXT NOT NULL,
                created_at TEXT NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_identity_revoked ON agent_identities(revoked)"
        )
        self._conn.commit()
        self._load_from_db()

    def _load_from_db(self) -> None:
        if not self._conn:
            return
        rows = self._conn.execute(
            "SELECT agent_id, capabilities, policy_version, metadata, created_at, revoked FROM agent_identities"
        ).fetchall()
        for row in rows:
            agent_id, caps_str, pv, meta_str, created_at, revoked = row
            caps = set(json.loads(caps_str))
            meta = json.loads(meta_str)
            identity = AgentIdentity(
                agent_id=agent_id,
                capabilities=caps,
                policy_version=pv,
                metadata=meta,
                created_at=created_at,
                revoked=bool(revoked),
            )
            self._identities[agent_id] = identity

    def _save_to_db(self, identity: AgentIdentity) -> None:
        if not self._conn:
            return
        self._conn.execute(
            "INSERT OR REPLACE INTO agent_identities (agent_id, capabilities, policy_version, metadata, created_at, revoked) VALUES (?, ?, ?, ?, ?, ?)",
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

    def register(
        self,
        agent_id: str | None = None,
        capabilities: list[str] | None = None,
        policy_version: str = "0",
        metadata: dict[str, Any] | None = None,
    ) -> AgentIdentity:
        identity = AgentIdentity(
            agent_id=agent_id or f"agent_{uuid.uuid4().hex[:12]}",
            capabilities=set(capabilities or []),
            policy_version=policy_version,
            metadata=metadata or {},
        )
        with self._lock:
            self._identities[identity.agent_id] = identity
            self._save_to_db(identity)
        return identity

    def get(self, agent_id: str) -> AgentIdentity | None:
        with self._lock:
            identity = self._identities.get(agent_id)
            if identity is None and self._conn:
                row = self._conn.execute(
                    "SELECT agent_id, capabilities, policy_version, metadata, created_at, revoked FROM agent_identities WHERE agent_id=?",
                    (agent_id,),
                ).fetchone()
                if row:
                    identity = AgentIdentity(
                        agent_id=row[0],
                        capabilities=set(json.loads(row[1])),
                        policy_version=row[2],
                        metadata=json.loads(row[3]),
                        created_at=row[4],
                        revoked=bool(row[5]),
                    )
            return identity

    def has_capability(self, agent_id: str, capability: str) -> bool:
        with self._lock:
            identity = self._identities.get(agent_id)
            if not identity or identity.revoked:
                return False
            return capability in identity.capabilities

    def grant(self, agent_id: str, capability: str) -> bool:
        with self._lock:
            identity = self._identities.get(agent_id)
            if not identity:
                return False
            identity.capabilities.add(capability)
            self._save_to_db(identity)
            return True

    def revoke(self, agent_id: str) -> bool:
        with self._lock:
            identity = self._identities.get(agent_id)
            if not identity:
                return False
            identity.revoked = True
            self._save_to_db(identity)
            return True

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            if self._conn:
                rows = self._conn.execute(
                    "SELECT agent_id, capabilities, policy_version, revoked FROM agent_identities"
                ).fetchall()
                return [
                    {
                        "agent_id": r[0],
                        "capabilities": json.loads(r[1]),
                        "policy_version": r[2],
                        "revoked": bool(r[3]),
                    }
                    for r in rows
                ]
            return [
                {
                    "agent_id": i.agent_id,
                    "capabilities": sorted(i.capabilities),
                    "policy_version": i.policy_version,
                    "revoked": i.revoked,
                }
                for i in self._identities.values()
            ]