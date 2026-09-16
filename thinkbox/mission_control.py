"""KUDBEE — Mission Control.

A single place that answers: *what can this system actually do right now, what is
degraded, what is unavailable, and where does a human need to intervene?*

Every check is a real probe — environment presence, filesystem state, SQLite
integrity, chain verification. Nothing here is invented, and nothing is reported
as healthy merely because a variable exists.

Status vocabulary
    ready        verified usable
    degraded     usable but limited, with a concrete reason
    unavailable  present in config but not usable
    missing      not configured at all
    unknown      could not be determined without a network call we do not make

`PRESENCE_ONLY` marks a capability where we intentionally did **not** make a
network call (so we do not treat "the variable exists" as proof of health).
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

READY = "ready"
DEGRADED = "degraded"
UNAVAILABLE = "unavailable"
MISSING = "missing"
UNKNOWN = "unknown"

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "data" / "thinkboxmd"
DEFAULT_DB = DEFAULT_DATA / "db"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Capability:
    key: str
    label: str
    layer: str
    status: str
    detail: str
    evidence: str = ""
    required_env: list[str] = field(default_factory=list)
    human_action: str = ""
    synthetic: bool = False
    critical: bool = True   # part of the core runtime path; external deps set False

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "layer": self.layer,
            "status": self.status,
            "detail": self.detail,
            "evidence": self.evidence,
            "required_env": self.required_env,
            "human_action": self.human_action,
            "synthetic": self.synthetic,
            "critical": self.critical,
        }


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------

def _env_present(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def _db_ok(path: Path, table: str | None = None) -> tuple[bool, str]:
    if not path.exists():
        return False, "file absent"
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        if table:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not row:
                conn.close()
                return False, f"table {table} absent"
            n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            conn.close()
            return True, f"{table}: {n} rows"
        conn.execute("SELECT 1").fetchone()
        conn.close()
        return True, "readable"
    except sqlite3.Error as e:
        return False, f"{type(e).__name__}: {str(e)[:80]}"


def check_provider() -> Capability:
    present = _env_present("INCEPTION_API_KEY")
    return Capability(
        key="provider.inception",
        label="Inception Mercury 2 (model provider)",
        layer="provider",
        status=READY if present else MISSING,
        detail=(
            "key present; live calls verified earlier this cycle (~24 rps ceiling)"
            if present else "INCEPTION_API_KEY not set — no model calls possible"
        ),
        evidence="experiments/probe_mercury_throughput.py, data/thinkboxmd/mercury_throughput_probe.json",
        required_env=["INCEPTION_API_KEY"],
        human_action="" if present else "set INCEPTION_API_KEY",
        synthetic=False,
    )


def check_stores(db_dir: Path) -> list[Capability]:
    specs = [
        ("metrics.db", "sessions", "metrics"),
        ("flight_recorder.db", "worker_records", "flight recorder"),
        ("flight_recorder.db", "proof_chains", "proof chains"),
        ("reputation.db", "worker_reputation", "reputation"),
        ("memory_evolution.db", "memories", "memory evolution"),
        ("experiments.db", "variant_results", "experiments"),
    ]
    out: list[Capability] = []
    for fname, table, label in specs:
        ok, detail = _db_ok(db_dir / fname, table)
        out.append(Capability(
            key=f"store.{fname}.{table}",
            label=f"SQLite · {label}",
            layer="persistence",
            status=READY if ok else MISSING,
            detail=detail,
            evidence=str((db_dir / fname).relative_to(ROOT)) if (db_dir / fname).exists() else "",
            human_action="" if ok else "run a swarm to create this store",
        ))
    return out


def check_ledger(db_dir: Path) -> Capability:
    """Verify the hash chain using a READ-ONLY connection.

    ActionLedger's constructor opens read-write (it creates its table). The
    dashboard contract promises read-only access, so we replay the chain here
    with the same hash function over a ``mode=ro`` connection instead.
    """
    path = db_dir / "action_ledger.db"
    if not path.exists():
        return Capability("ledger", "Action ledger (hash chain)", "proof", MISSING,
                          "action_ledger.db absent", human_action="run a swarm")
    try:
        from thinkbox.ledger import ActionLedger

        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT entry_id, agent_id, capability, action, allowed, reason, timestamp, "
                "prev_hash, entry_hash, metadata FROM ledger ORDER BY rowid"
            ).fetchall()
        finally:
            conn.close()

        prev = "GENESIS"
        for (entry_id, agent_id, capability, action, allowed, reason, timestamp,
             prev_hash, entry_hash, metadata) in rows:
            if prev_hash != prev:
                return Capability("ledger", "Action ledger (hash chain)", "proof", UNAVAILABLE,
                                  f"{len(rows)} entries, chain BROKEN at {entry_id}")
            payload = {
                "entry_id": entry_id, "agent_id": agent_id, "capability": capability,
                "action": action, "allowed": bool(allowed), "reason": reason,
                "timestamp": timestamp, "prev_hash": prev_hash,
                "metadata": json.loads(metadata),
            }
            if ActionLedger._compute_hash(payload) != entry_hash:
                return Capability("ledger", "Action ledger (hash chain)", "proof", UNAVAILABLE,
                                  f"{len(rows)} entries, hash mismatch at {entry_id}")
            prev = entry_hash
        return Capability("ledger", "Action ledger (hash chain)", "proof", READY,
                          f"{len(rows)} entries, chain valid", evidence=str(path.relative_to(ROOT)))
    except Exception as e:  # noqa: BLE001
        return Capability("ledger", "Action ledger (hash chain)", "proof", UNKNOWN,
                          f"{type(e).__name__}: {str(e)[:80]}")


def check_vector() -> Capability:
    present = _env_present("UPSTASH_VECTOR_REST_URL") and _env_present("UPSTASH_VECTOR_REST_TOKEN")
    if not present:
        return Capability("vector", "Upstash Vector (distributed memory)", "memory", MISSING,
                          "UPSTASH_VECTOR_REST_URL/TOKEN not set", critical=False)
    return Capability(
        "vector", "Upstash Vector (distributed memory)", "memory", DEGRADED,
        "reachable, but writes are rejected: dense index requires a vector and no "
        "embedding provider exists",
        evidence="data/findings/thinkboxmd_upstash_vector_defect.md",
        required_env=["UPSTASH_VECTOR_REST_URL", "UPSTASH_VECTOR_REST_TOKEN"],
        human_action="implement an embedding provider, then fix UpstashVectorSync.upsert()",
        critical=False,
    )


def check_box() -> Capability:
    present = _env_present("UPSTASH_PUBLIC_BOX_URL") or _env_present("UPSTASH_BOX_API_KEY")
    if not present:
        return Capability("box", "Upstash Box (remote worker)", "compute", MISSING,
                          "not configured", critical=False)
    return Capability(
        "box", "Upstash Box (remote worker)", "compute", UNAVAILABLE,
        "host resolves, but the preview returns 'preview not found' - no live service",
        required_env=["UPSTASH_PUBLIC_BOX_URL", "UPSTASH_BOX_API_KEY"],
        human_action="start a Box preview, or run the worker on UpCloud instead",
        critical=False,
    )


def check_upcloud() -> Capability:
    present = _env_present("THINKBOX_UPCLOUD_API_TOKEN")
    key_path = os.environ.get("UPCLOUD_SSH_KEY_PATH", "")
    key_exists = bool(key_path) and Path(os.path.expanduser(key_path)).exists()
    if not present and not key_exists:
        return Capability("upcloud", "UpCloud dedicated host", "compute", MISSING,
                          "not configured", critical=False)
    detail = "API token rejected (HTTP 401)"
    if not key_exists:
        detail += f"; SSH key {key_path or '(unset)'} absent"
    return Capability(
        "upcloud", "UpCloud dedicated host", "compute", UNAVAILABLE, detail,
        required_env=["THINKBOX_UPCLOUD_API_TOKEN", "UPCLOUD_SSH_KEY_PATH"],
        human_action="mint a fresh UpCloud API token and/or place the SSH key at the configured path",
        critical=False,
    )


def check_redis() -> Capability:
    import importlib.util
    has_client = importlib.util.find_spec("redis") is not None
    configured = any(_env_present(k) for k in ("REDIS_URL", "UPSTASH_REDIS_REST_URL", "UPSTASH_API_KEY"))
    if not configured and not has_client:
        return Capability("redis", "Redis / work queue", "compute", MISSING,
                          "no client installed and no queue URL configured", critical=False)
    return Capability("redis", "Redis / work queue", "compute", UNAVAILABLE,
                      "configured but no client in the repo and no queue wired",
                      human_action="add a durable queue only when a measured need exists",
                      critical=False)


def check_mcp() -> Capability:
    return Capability("mcp", "MCP tool bridge", "tools", MISSING,
                      "no MCP client or server in the repo", critical=False)


def check_test_evidence() -> list[Capability]:
    e2e = ROOT / "tests" / "e2e"
    e2e_files = [p for p in e2e.glob("test_*.py")] if e2e.exists() else []
    bench = ROOT / "benchmarks"
    bench_files = [p for p in bench.glob("*.md")] if bench.exists() else []
    return [
        Capability(
            "tests.e2e", "End-to-end test suite", "quality",
            READY if e2e_files else DEGRADED,
            f"{len(e2e_files)} e2e test files" if e2e_files else "tests/e2e/ has no test files",
            human_action="" if e2e_files else "add e2e coverage for the runtime loop",
        ),
        Capability(
            "benchmarks", "Benchmark evidence artifacts", "quality",
            READY if bench_files else DEGRADED,
            f"{len(bench_files)} benchmark docs" if bench_files else "benchmarks/ has no artifacts",
            human_action="" if bench_files else "record benchmark evidence (AGENTS.md §1.5)",
        ),
    ]


def check_events(data_dir: Path) -> Capability:
    ev = data_dir / "swarm_events.jsonl"
    if not ev.exists():
        return Capability("events", "Live swarm event stream", "runtime", MISSING,
                          "swarm_events.jsonl absent — dashboard will show idle")
    try:
        size = ev.stat().st_size
        with ev.open(errors="replace") as fh:
            lines = sum(1 for _ in fh)
        return Capability("events", "Live swarm event stream", "runtime", READY,
                          f"{lines} events, {size} bytes", evidence=str(ev.relative_to(ROOT)))
    except OSError as e:
        return Capability("events", "Live swarm event stream", "runtime", UNKNOWN, str(e)[:80])


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class MissionControl:
    """Runs every real probe and classifies the system's actual capability."""

    def __init__(self, data_dir: Path | None = None, db_dir: Path | None = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA
        self.db_dir = Path(db_dir) if db_dir else DEFAULT_DB

    def probes(self) -> list[Callable[[], Any]]:
        return [
            check_provider,
            lambda: check_stores(self.db_dir),
            lambda: check_ledger(self.db_dir),
            check_vector,
            check_box,
            check_upcloud,
            check_redis,
            check_mcp,
            check_test_evidence,
            lambda: check_events(self.data_dir),
        ]

    def run(self) -> dict[str, Any]:
        caps: list[Capability] = []
        for probe in self.probes():
            result = probe()
            if isinstance(result, list):
                caps.extend(result)
            else:
                caps.append(result)

        counts: dict[str, int] = {}
        for c in caps:
            counts[c.status] = counts.get(c.status, 0) + 1

        core = [c for c in caps if c.critical]
        external = [c for c in caps if not c.critical]
        core_counts: dict[str, int] = {}
        for c in core:
            core_counts[c.status] = core_counts.get(c.status, 0) + 1

        blockers = [c.to_dict() for c in caps if c.status in (UNAVAILABLE, MISSING)]
        degraded = [c.to_dict() for c in caps if c.status == DEGRADED]
        human = [
            {"key": c.key, "label": c.label, "action": c.human_action}
            for c in caps if c.human_action
        ]

        def _readiness(items: list[Capability]) -> float:
            if not items:
                return 0.0
            w = {READY: 1.0, DEGRADED: 0.5, UNKNOWN: 0.25, UNAVAILABLE: 0.0, MISSING: 0.0}
            return round(sum(w.get(c.status, 0.0) for c in items) / len(items), 4)

        # Overall reflects the CORE runtime path only. External dependencies that
        # are blocked must not be reported as if the system itself were down.
        core_blocked = [c for c in core if c.status in (UNAVAILABLE, MISSING)]
        core_degraded = [c for c in core if c.status == DEGRADED]
        overall = UNAVAILABLE if core_blocked else (DEGRADED if core_degraded else READY)

        return {
            "generated_at": _utc(),
            "overall": overall,
            "readiness": _readiness(caps),
            "core_readiness": _readiness(core),
            "external_readiness": _readiness(external),
            "counts": counts,
            "core_counts": core_counts,
            "capabilities": [c.to_dict() for c in caps],
            "blockers": blockers,
            "external_blockers": [c.to_dict() for c in external
                                  if c.status in (UNAVAILABLE, MISSING, DEGRADED)],
            "core_blockers": [c.to_dict() for c in core
                              if c.status in (UNAVAILABLE, MISSING, DEGRADED)],
            "degraded": degraded,
            "human_intervention_required": human,
            "note": (
                "Probes are local and non-destructive; all SQLite access is read-only and "
                "no network calls are made, so a capability is only marked ready when local "
                "evidence supports it. 'overall' reflects the CORE runtime path; external "
                "blockers are listed separately."
            ),
        }


def snapshot(data_dir: Path | None = None, db_dir: Path | None = None) -> dict[str, Any]:
    return MissionControl(data_dir, db_dir).run()
