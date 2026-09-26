"""Durable append-only store for autonomous-loop action receipts (PR #251).

Loop actions are side effects recorded against a loop (start/stop/run/reset).
Before this module they lived only in ``DashboardState.loop_actions`` and were
lost on restart, which meant the audit trail for operator actions was ephemeral.

This store persists every action to SQLite in an append-only table with a
tamper-evident hash chain, mirroring the ``ActionReceiptStore`` pattern used by
the agent control plane: each row carries its own ``entry_hash`` computed over
the payload including the previous row's hash, so any edit, deletion, or
reordering breaks verification.

Evidence note: receipts are ``simulated`` by default (the action was *requested*
through the control plane); nothing here claims the loop actually performed an
observable physical side effect.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from thinkbox.sqlite_pragmas import open_sqlite

logger = logging.getLogger(__name__)

GENESIS_HASH = "GENESIS"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS loop_action_receipts (
    receipt_id TEXT PRIMARY KEY,
    loop_id TEXT NOT NULL,
    action TEXT NOT NULL,
    source TEXT NOT NULL,
    evidence_label TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    result TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL,
    loop_action_id TEXT NOT NULL
)
"""


@dataclass
class LoopActionReceipt:
    """Durable receipt for one recorded autonomous-loop action."""

    receipt_id: str
    loop_id: str
    action: str
    source: str
    evidence_label: str
    timestamp: str
    prev_hash: str
    entry_hash: str
    result: dict[str, Any] = field(default_factory=dict)
    loop_action_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize the receipt to a plain dict."""
        return {
            "receipt_id": self.receipt_id,
            "loop_id": self.loop_id,
            "action": self.action,
            "source": self.source,
            "evidence_label": self.evidence_label,
            "timestamp": self.timestamp,
            "prev_hash": self.prev_hash,
            "entry_hash": self.entry_hash,
            "result": self.result,
            "loop_action_id": self.loop_action_id,
        }


class LoopActionStore:
    """Append-only SQLite store for loop action receipts with hash-chain integrity.

    Thread-safe by construction: every read/write runs under a single lock and
    the connection is opened with ``check_same_thread=False`` so it can be shared
    with an async/API caller thread.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._path = str(db_path)
        self._lock = threading.Lock()
        self._conn = open_sqlite(self._path, check_same_thread=False, foreign_keys=False)
        with self._lock:
            self._conn.execute(_CREATE_TABLE)
            self._conn.commit()

    @property
    def path(self) -> str:
        """Return the SQLite path backing this store."""
        return self._path

    def append(
        self,
        loop_id: str,
        action: str,
        result: Any = None,
        source: str = "",
        evidence_label: str = "simulated",
        loop_action_id: str = "",
    ) -> LoopActionReceipt:
        """Append one action receipt and return it.

        The receipt's hash covers the payload plus the previous chain head, so
        the row cannot be edited, dropped, or reordered without detection.
        """
        head = self._chain_head()
        receipt_id = f"lar_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()
        result_payload = result if isinstance(result, dict) else {"value": result}
        if result is None:
            result_payload = {}
        payload = {
            "receipt_id": receipt_id,
            "loop_id": loop_id,
            "action": action,
            "source": source,
            "evidence_label": evidence_label,
            "timestamp": timestamp,
            "result": result_payload,
            "loop_action_id": loop_action_id,
            "prev_hash": head,
        }
        entry_hash = self._compute_hash(payload)
        payload["entry_hash"] = entry_hash

        with self._lock:
            self._conn.execute(
                "INSERT INTO loop_action_receipts "
                "(receipt_id, loop_id, action, source, evidence_label, timestamp, "
                " result, prev_hash, entry_hash, loop_action_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    receipt_id,
                    loop_id,
                    action,
                    source,
                    evidence_label,
                    timestamp,
                    json.dumps(result_payload, default=str),
                    head,
                    entry_hash,
                    loop_action_id,
                ),
            )
            self._conn.commit()
        logger.info(
            "Appended loop action receipt %s for loop %s action %s",
            receipt_id,
            loop_id,
            action,
        )
        return LoopActionReceipt(**payload)

    def verify(self) -> bool:
        """Verify the full hash chain. False if any row was tampered with."""
        rows = self._rows()
        prev = GENESIS_HASH
        for row in rows:
            (
                receipt_id,
                loop_id,
                action,
                source,
                evidence_label,
                timestamp,
                result_str,
                prev_hash,
                entry_hash,
                loop_action_id,
            ) = row
            if prev_hash != prev:
                return False
            payload = {
                "receipt_id": receipt_id,
                "loop_id": loop_id,
                "action": action,
                "source": source,
                "evidence_label": evidence_label,
                "timestamp": timestamp,
                "result": json.loads(result_str),
                "loop_action_id": loop_action_id,
                "prev_hash": prev_hash,
            }
            if self._compute_hash(payload) != entry_hash:
                return False
            prev = entry_hash
        return True

    def _rows(self) -> list[tuple[Any, ...]]:
        with self._lock:
            return list(
                self._conn.execute(
                    "SELECT receipt_id, loop_id, action, source, evidence_label, "
                    "timestamp, result, prev_hash, entry_hash, loop_action_id "
                    "FROM loop_action_receipts ORDER BY rowid"
                ).fetchall()
            )

    def _chain_head(self) -> str:
        with self._lock:
            row = self._conn.execute(
                "SELECT entry_hash FROM loop_action_receipts ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
        return row[0] if row else GENESIS_HASH

    def all_receipts(self, limit: int | None = None) -> list[LoopActionReceipt]:
        """Return every receipt in insertion order (oldest first).

        This is the read path used to rebuild in-memory state after a restart.
        """
        rows = self._rows()
        if limit is not None:
            rows = rows[:limit]
        return [self._to_receipt(r) for r in rows]

    def latest(self, n: int = 10) -> list[LoopActionReceipt]:
        """Return the n most recent receipts, newest first."""
        rows = self._rows()
        return [self._to_receipt(r) for r in rows[-n:]][::-1]

    def by_loop(self, loop_id: str, limit: int = 50) -> list[LoopActionReceipt]:
        """Return receipts for one loop, oldest first."""
        rows = [r for r in self._rows() if r[1] == loop_id]
        return [self._to_receipt(r) for r in rows[:limit]]

    def count(self) -> int:
        """Return the total number of persisted receipts."""
        with self._lock:
            return int(
                self._conn.execute("SELECT COUNT(*) FROM loop_action_receipts").fetchone()[0]
            )

    def close(self) -> None:
        """Close the underlying connection."""
        with self._lock:
            self._conn.close()

    def _to_receipt(self, row: tuple[Any, ...]) -> LoopActionReceipt:
        (
            receipt_id,
            loop_id,
            action,
            source,
            evidence_label,
            timestamp,
            result_str,
            prev_hash,
            entry_hash,
            loop_action_id,
        ) = row
        return LoopActionReceipt(
            receipt_id=receipt_id,
            loop_id=loop_id,
            action=action,
            source=source,
            evidence_label=evidence_label,
            timestamp=timestamp,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
            result=json.loads(result_str),
            loop_action_id=loop_action_id,
        )

    @staticmethod
    def _compute_hash(payload: dict[str, Any]) -> str:
        body = json.dumps(payload, sort_keys=True, default=str).encode()
        return hashlib.sha256(body).hexdigest()[:32]


def default_loop_action_db_path() -> Path:
    """Return the default SQLite path for durable loop action receipts."""
    return Path("data/thinkboxmd/db/loop_actions.db")


LOOP_ACTION_DB_ENV = "THINKBOX_LOOP_ACTION_DB"

_DISABLED_VALUES = {"off", "0", "false", "none", "disabled"}


def resolve_loop_action_db_path(env: Mapping[str, str] | None = None) -> str | None:
    """Resolve the loop action DB path from configuration.

    Reads ``THINKBOX_LOOP_ACTION_DB``:
      * unset/empty        -> the default durable path
      * off/0/false/none   -> ``None`` (durability explicitly disabled)
      * ``:memory:``       -> in-memory (ephemeral, for tests)
      * anything else      -> that filesystem path

    Returning ``None`` for the disabled case is deliberate: callers must be able
    to distinguish "disabled" from "use the default".
    """
    source = os.environ if env is None else env
    raw = (source.get(LOOP_ACTION_DB_ENV) or "").strip()
    if not raw:
        return str(default_loop_action_db_path())
    if raw.lower() in _DISABLED_VALUES:
        return None
    return raw


def attach_durable_loop_actions(
    state: Any,
    db_path: str | Path | None = None,
    *,
    hydrate: bool = True,
) -> tuple[Any, int]:
    """Attach a durable loop action store to dashboard state and recover history.

    Convenience wrapper for startup wiring: it opens the store, attaches it so
    future ``record_loop_action`` calls persist, and by default replays existing
    receipts back into memory so history recorded before a restart is visible.

    Returns ``(store, restored_count)``. Raises nothing for storage problems on
    hydration (handled internally and reported as a count of 0).
    """
    target = db_path if db_path is not None else default_loop_action_db_path()
    store = open_loop_action_store(target)
    state.set_loop_action_store(store)
    restored = state.hydrate_loop_actions_from_store() if hydrate else 0
    return store, restored


def maybe_attach_loop_action_store(
    state: Any,
    env: Mapping[str, str] | None = None,
    *,
    hydrate: bool = True,
) -> Any:
    """Attach a durable store only when durability is enabled by configuration.

    Honours :func:`resolve_loop_action_db_path`. Returns the attached store, or
    ``None`` when ``THINKBOX_LOOP_ACTION_DB`` disables durability — letting the
    caller continue without an audit trail rather than silently creating one.
    """
    resolved = resolve_loop_action_db_path(env)
    if resolved is None:
        logger.info("Loop action durability disabled via %s", LOOP_ACTION_DB_ENV)
        return None
    store, restored = attach_durable_loop_actions(state, resolved, hydrate=hydrate)
    logger.info(
        "Loop action durability enabled at %s (%d action(s) recovered)",
        resolved,
        restored,
    )
    return store


def open_loop_action_store(db_path: str | Path | None = None) -> LoopActionStore:
    """Open a loop action store, creating the parent directory when needed."""
    path = Path(db_path) if db_path else default_loop_action_db_path()
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    return LoopActionStore(path)
