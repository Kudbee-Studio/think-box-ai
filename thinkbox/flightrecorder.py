"""KUDBEE — Swarm Flight Recorder, Proof-Carrying Decisions, and Swarm Genomes.

Three related instruments, all on SQLite (free, zero-config, always available):

  1. Flight Recorder — every worker call is a permanent record: session id,
     worker id, trace id, model, prompt version, tokens, latency, decision,
     challenge, validator result, evidence refs, and final outcome.

  2. Proof-Carrying Decisions — a machine-verifiable chain
     claim -> evidence -> workers -> challenges -> validators -> decision -> proof.
     Anyone can recompute the hash and inspect why the swarm believes something.

  3. Swarm Genome / Replay — the complete configuration of a run (workers,
     model, prompts, memory snapshot, validators, concurrency, timing) so a
     past swarm can be reproduced and independently verified.
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

DEFAULT_DB = "data/thinkboxmd/db/flight_recorder.db"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_hash(payload: Any) -> str:
    """Deterministic SHA-256 over canonical JSON. Used for every proof node."""
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(body).hexdigest()


# ---------------------------------------------------------------------------
# 1. Flight Recorder
# ---------------------------------------------------------------------------

@dataclass
class WorkerRecord:
    """One permanent, complete record per worker call. Nothing disappears."""

    session_id: str
    worker_id: str
    role: str
    model: str
    prompt_version: str
    trace_id: str = ""
    box_id: str = ""
    claim_id: str = ""
    capability: str = ""
    temperature: float = 0.0
    max_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    latency_s: float = 0.0
    decision: str = ""            # tier the worker chose
    challenge: str = ""           # what it challenged, if anything
    validator_result: str = ""    # verdict from a validator, if validated
    evidence_refs: list[str] = field(default_factory=list)
    outcome: str = ""             # ok | error
    error: str = ""
    cost_usd: float = 0.0
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "worker_id": self.worker_id,
            "role": self.role,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "trace_id": self.trace_id,
            "box_id": self.box_id,
            "claim_id": self.claim_id,
            "capability": self.capability,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "total_tokens": self.total_tokens,
            "latency_s": round(self.latency_s, 4),
            "decision": self.decision,
            "challenge": self.challenge,
            "validator_result": self.validator_result,
            "evidence_refs": list(self.evidence_refs),
            "outcome": self.outcome,
            "error": self.error,
            "cost_usd": round(self.cost_usd, 8),
            "created_at": self.created_at or _utc(),
        }


class FlightRecorder:
    """Durable black-box recorder for every worker call."""

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
                CREATE TABLE IF NOT EXISTS worker_records (
                    record_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    role TEXT, model TEXT, prompt_version TEXT,
                    trace_id TEXT, box_id TEXT, claim_id TEXT, capability TEXT,
                    temperature REAL, max_tokens INTEGER,
                    prompt_tokens INTEGER, completion_tokens INTEGER,
                    reasoning_tokens INTEGER, total_tokens INTEGER,
                    latency_s REAL, decision TEXT, challenge TEXT,
                    validator_result TEXT, evidence_refs TEXT,
                    outcome TEXT, error TEXT, cost_usd REAL,
                    created_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_fr_session ON worker_records(session_id);
                CREATE INDEX IF NOT EXISTS idx_fr_worker ON worker_records(worker_id);

                CREATE TABLE IF NOT EXISTS proof_chains (
                    chain_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    claim_id TEXT NOT NULL,
                    claim TEXT,
                    decision TEXT,
                    node_count INTEGER,
                    chain_hash TEXT NOT NULL,
                    created_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_pc_session ON proof_chains(session_id);

                CREATE TABLE IF NOT EXISTS proof_nodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chain_id TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    node_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    node_hash TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_pn_chain ON proof_nodes(chain_id);

                CREATE TABLE IF NOT EXISTS genomes (
                    genome_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    gene TEXT NOT NULL,
                    genome_hash TEXT NOT NULL,
                    created_at TEXT
                );
                """
            )
            self._conn.commit()

    # -- records -----------------------------------------------------------

    def record(self, rec: WorkerRecord) -> str:
        rec_id = f"fr_{rec.session_id}_{rec.worker_id}"
        d = rec.to_dict()
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO worker_records (record_id, session_id, worker_id, role, "
                "model, prompt_version, trace_id, box_id, claim_id, capability, temperature, "
                "max_tokens, prompt_tokens, completion_tokens, reasoning_tokens, total_tokens, "
                "latency_s, decision, challenge, validator_result, evidence_refs, outcome, error, "
                "cost_usd, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    rec_id, d["session_id"], d["worker_id"], d["role"], d["model"],
                    d["prompt_version"], d["trace_id"], d["box_id"], d["claim_id"],
                    d["capability"], d["temperature"], d["max_tokens"], d["prompt_tokens"],
                    d["completion_tokens"], d["reasoning_tokens"], d["total_tokens"],
                    d["latency_s"], d["decision"], d["challenge"], d["validator_result"],
                    json.dumps(d["evidence_refs"]), d["outcome"], d["error"], d["cost_usd"],
                    d["created_at"],
                ),
            )
            self._conn.commit()
        return rec_id

    def session_records(self, session_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM worker_records WHERE session_id = ? ORDER BY created_at",
                (session_id,),
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["evidence_refs"] = json.loads(d.get("evidence_refs") or "[]")
            except json.JSONDecodeError:
                d["evidence_refs"] = []
            out.append(d)
        return out

    def count(self, session_id: str | None = None) -> int:
        with self._lock:
            if session_id:
                row = self._conn.execute(
                    "SELECT COUNT(*) n FROM worker_records WHERE session_id=?", (session_id,)
                ).fetchone()
            else:
                row = self._conn.execute("SELECT COUNT(*) n FROM worker_records").fetchone()
        return row["n"] or 0

    # -- 2. Proof-carrying decisions ---------------------------------------

    def build_proof_chain(
        self,
        session_id: str,
        claim_id: str,
        claim: str,
        evidence_nodes: list[dict[str, Any]],
        worker_nodes: list[dict[str, Any]],
        challenge_nodes: list[dict[str, Any]],
        validator_nodes: list[dict[str, Any]],
        decision: str,
    ) -> dict[str, Any]:
        """Materialise claim -> evidence -> workers -> challenges -> validators -> decision -> proof."""
        chain_id = f"pc_{session_id}_{claim_id}"
        ordered: list[tuple[str, dict[str, Any]]] = [
            ("claim", {"claim_id": claim_id, "claim": claim}),
            *[("evidence", e) for e in evidence_nodes],
            *[("worker", w) for w in worker_nodes],
            *[("challenge", c) for c in challenge_nodes],
            *[("validator", v) for v in validator_nodes],
            ("decision", {"decision": decision}),
        ]

        prev = "GENESIS"
        nodes: list[dict[str, Any]] = []
        with self._lock:
            self._conn.execute("DELETE FROM proof_nodes WHERE chain_id=?", (chain_id,))
            for ordinal, (ntype, payload) in enumerate(ordered):
                node_hash = canonical_hash({"prev": prev, "ordinal": ordinal, "type": ntype, "payload": payload})
                self._conn.execute(
                    "INSERT INTO proof_nodes (chain_id, ordinal, node_type, payload, node_hash) "
                    "VALUES (?,?,?,?,?)",
                    (chain_id, ordinal, ntype, json.dumps(payload, sort_keys=True, default=str), node_hash),
                )
                nodes.append({"ordinal": ordinal, "type": ntype, "payload": payload, "hash": node_hash})
                prev = node_hash

            chain_hash = canonical_hash({"nodes": [{"ordinal": n["ordinal"], "hash": n["hash"]} for n in nodes]})
            self._conn.execute(
                "INSERT OR REPLACE INTO proof_chains (chain_id, session_id, claim_id, claim, decision, "
                "node_count, chain_hash, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (chain_id, session_id, claim_id, claim, decision, len(nodes), chain_hash, _utc()),
            )
            self._conn.commit()
        return {"chain_id": chain_id, "nodes": nodes, "chain_hash": chain_hash, "node_count": len(nodes)}

    def verify_proof_chain(self, chain_id: str) -> bool:
        """Recompute the whole chain from stored nodes; detects any tampering."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT ordinal, node_type, payload, node_hash FROM proof_nodes "
                "WHERE chain_id=? ORDER BY ordinal",
                (chain_id,),
            ).fetchall()
            chain = self._conn.execute(
                "SELECT chain_hash FROM proof_chains WHERE chain_id=?", (chain_id,)
            ).fetchone()
        if not chain:
            return False
        prev = "GENESIS"
        hashes: list[dict[str, Any]] = []
        for r in rows:
            payload = json.loads(r["payload"])
            expect = canonical_hash({"prev": prev, "ordinal": r["ordinal"], "type": r["node_type"], "payload": payload})
            if expect != r["node_hash"]:
                return False
            hashes.append({"ordinal": r["ordinal"], "hash": r["node_hash"]})
            prev = r["node_hash"]
        return canonical_hash({"nodes": hashes}) == chain["chain_hash"]

    def explain(self, chain_id: str) -> dict[str, Any]:
        """Human-readable 'why does the swarm believe this?'."""
        with self._lock:
            chain = self._conn.execute("SELECT * FROM proof_chains WHERE chain_id=?", (chain_id,)).fetchone()
            nodes = self._conn.execute(
                "SELECT ordinal, node_type, payload FROM proof_nodes WHERE chain_id=? ORDER BY ordinal",
                (chain_id,),
            ).fetchall()
        if not chain:
            return {}
        summary: dict[str, list[Any]] = {}
        for n in nodes:
            summary.setdefault(n["node_type"], []).append(json.loads(n["payload"]))
        return {
            "chain_id": chain_id,
            "claim": chain["claim"],
            "decision": chain["decision"],
            "verified": self.verify_proof_chain(chain_id),
            "chain_hash": chain["chain_hash"],
            "counts": {k: len(v) for k, v in summary.items()},
            "evidence": summary.get("evidence", []),
            "workers": summary.get("worker", []),
            "challenges": summary.get("challenge", []),
            "validators": summary.get("validator", []),
        }

    # -- 3. Genome / replay -------------------------------------------------

    def save_genome(self, session_id: str, gene: dict[str, Any]) -> dict[str, Any]:
        genome_hash = canonical_hash(gene)
        genome_id = f"gen_{session_id}"
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO genomes (genome_id, session_id, gene, genome_hash, created_at) "
                "VALUES (?,?,?,?,?)",
                (genome_id, session_id, json.dumps(gene, sort_keys=True, default=str), genome_hash, _utc()),
            )
            self._conn.commit()
        return {"genome_id": genome_id, "genome_hash": genome_hash, "gene": gene}

    def load_genome(self, session_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT gene, genome_hash FROM genomes WHERE session_id=?", (session_id,)
            ).fetchone()
        if not row:
            return None
        return {"gene": json.loads(row["gene"]), "genome_hash": row["genome_hash"]}

    def verify_genome(self, session_id: str) -> bool:
        loaded = self.load_genome(session_id)
        if not loaded:
            return False
        return canonical_hash(loaded["gene"]) == loaded["genome_hash"]
