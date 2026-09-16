"""KUDBEE — durable swarm/work telemetry on SQLite.

Free, zero-config, always-available by design: SQLite from the standard library,
the same persistence choice as `thinkbox/ledger.py` and `thinkbox/workspace.py`.
No server to run, no account, no network — and it can be swapped for a hosted
Postgres/Redis later without changing the call sites.

Records, per run:
  * session header (id, kind, model, wall time, throughput, ledger integrity)
  * per-call token usage (prompt / completion / reasoning / total)
  * challenge outcomes (primary tier vs validator tier, disagreement, inflation)
  * a transparent strength score with history, so "are we getting stronger?"
    is answered by a measured delta rather than a claim.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB = "data/thinkboxmd/db/metrics.db"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SwarmStrengthIndex:
    """THINK Swarm Strength Index (TSSI).

    Measures improving *evidence-backed decision quality* across runs — not how
    busy the swarm was and not how confident it sounded.

    Deliberately NOT penalised (these are signals to report, not defects):
      * challenge activity — how often validators disagreed with primaries
      * validator tier inflation — a governance signal about the reviewer

    Components (each already in [0,1], all auditable):
      reliability            ok / total calls
      grounding              grounded traces / traces
      evidence_quality       tier-weighted, credits honest UNVERIFIED
      challenge_resolution   of challenged claims, share that produced a
                             corrective (more-skeptical) validator signal
      validator_calibration  share of validators that did not inflate
      reproducibility        distribution stability vs the previous run
    Reported alongside, never folded in (avoids double counting):
      learning_delta         index now − index previous run
    """

    reliability: float
    grounding: float
    evidence_quality: float
    challenge_resolution: float
    validator_calibration: float
    reproducibility: float
    score: float
    # signals (reported, not scored)
    challenge_activity: float = 0.0
    tier_inflation_rate: float = 0.0
    learning_delta: float | None = None
    tier_distribution: dict[str, int] = field(default_factory=dict)
    components: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": round(self.score, 4),
            "components": {k: round(v, 4) for k, v in self.components.items()},
            "signals": {
                "challenge_activity": round(self.challenge_activity, 4),
                "tier_inflation_rate": round(self.tier_inflation_rate, 4),
            },
            "learning_delta": self.learning_delta,
            "tier_distribution": self.tier_distribution,
        }


TSSI_WEIGHTS = {
    "reliability": 0.18,
    "grounding": 0.20,
    "evidence_quality": 0.16,
    "challenge_resolution": 0.16,
    "validator_calibration": 0.14,
    "reproducibility": 0.16,
}

# Credit for an honest tier. UNVERIFIED is not zero: correctly refusing to
# over-claim is a real, desirable outcome on a synthetic corpus.
TIER_CREDIT = {"EVIDENCE": 1.0, "INFERENCE": 0.6, "HYPOTHESIS": 0.3, "UNVERIFIED": 0.15}


def _distribution_stability(current: dict[str, int], previous: dict[str, int] | None) -> float:
    """1 - total-variation distance between two tier distributions."""
    if not previous:
        return 0.5  # unknown history: neutral, never a penalty
    keys = set(current) | set(previous)
    ca, pa = sum(current.values()) or 1, sum(previous.values()) or 1
    tvd = 0.5 * sum(abs(current.get(k, 0) / ca - previous.get(k, 0) / pa) for k in keys)
    return max(0.0, 1.0 - tvd)


def compute_swarm_strength(
    total: int,
    ok: int,
    traces: int,
    grounded: int,
    validators: int,
    disagreements: int,
    validator_downgrades: int,
    tier_inflation: int,
    tier_distribution: dict[str, int],
    previous_distribution: dict[str, int] | None = None,
    previous_index: float | None = None,
) -> SwarmStrengthIndex:
    """Compute the TSSI from measured counters only."""
    reliability = (ok / total) if total else 0.0
    grounding = (grounded / traces) if traces else 0.0

    non_error = {k: v for k, v in tier_distribution.items() if k != "ERROR"}
    ne = sum(non_error.values()) or 1
    evidence_quality = sum(TIER_CREDIT.get(t, 0.0) * v for t, v in non_error.items()) / ne

    # Challenge resolution: a disagreement is productive when the validator
    # produced a corrective (more-skeptical) or equal signal. Noise (validator
    # inflating) is counted separately as an inflation signal.
    if disagreements:
        corrective = min(validator_downgrades, disagreements)
        challenge_resolution = corrective / disagreements
    else:
        # no disagreements => nothing was resolved; neutral-positive, not zero,
        # because a clean sweep is a valid outcome.
        challenge_resolution = 0.5

    validator_calibration = max(0.0, 1.0 - (tier_inflation / validators)) if validators else 0.0
    reproducibility = _distribution_stability(tier_distribution, previous_distribution)

    parts = {
        "reliability": reliability,
        "grounding": grounding,
        "evidence_quality": evidence_quality,
        "challenge_resolution": challenge_resolution,
        "validator_calibration": validator_calibration,
        "reproducibility": reproducibility,
    }
    score = sum(TSSI_WEIGHTS[k] * v for k, v in parts.items())
    delta = None if previous_index is None else round(score - previous_index, 4)

    return SwarmStrengthIndex(
        reliability=reliability,
        grounding=grounding,
        evidence_quality=evidence_quality,
        challenge_resolution=challenge_resolution,
        validator_calibration=validator_calibration,
        reproducibility=reproducibility,
        score=score,
        challenge_activity=(disagreements / validators) if validators else 0.0,
        tier_inflation_rate=(tier_inflation / validators) if validators else 0.0,
        learning_delta=delta,
        tier_distribution=dict(tier_distribution),
        components={k: round(v, 4) for k, v in parts.items()},
    )


# Backwards-compatible alias (older call sites)
compute_strength = compute_swarm_strength
StrengthScore = SwarmStrengthIndex


class MetricsStore:
    """SQLite-backed session / token / challenge / strength telemetry."""

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
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    model TEXT,
                    started_at TEXT,
                    ended_at TEXT,
                    workers_total INTEGER DEFAULT 0,
                    workers_ok INTEGER DEFAULT 0,
                    workers_failed INTEGER DEFAULT 0,
                    concurrency INTEGER DEFAULT 0,
                    wall_seconds REAL DEFAULT 0,
                    effective_rps REAL DEFAULT 0,
                    ledger_entries INTEGER DEFAULT 0,
                    ledger_valid INTEGER DEFAULT 0,
                    proof_hash TEXT,
                    strength_score REAL,
                    metadata TEXT
                );

                CREATE TABLE IF NOT EXISTS token_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    worker_id TEXT,
                    role TEXT,
                    model TEXT,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    reasoning_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    latency_s REAL DEFAULT 0,
                    ok INTEGER DEFAULT 0,
                    created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS challenges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    claim_id TEXT,
                    primary_tier TEXT,
                    validator_tier TEXT,
                    disagreed INTEGER DEFAULT 0,
                    validator_more_skeptical INTEGER DEFAULT 0,
                    created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS strength_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    created_at TEXT,
                    strength_score REAL,
                    grounded_ratio REAL,
                    evidence_ratio REAL,
                    challenge_rate REAL,
                    error_rate REAL,
                    tier_inflation_rate REAL,
                    tier_distribution TEXT,
                    learning_delta REAL
                );

                CREATE INDEX IF NOT EXISTS idx_tokens_session ON token_usage(session_id);
                CREATE INDEX IF NOT EXISTS idx_challenges_session ON challenges(session_id);
                CREATE INDEX IF NOT EXISTS idx_strength_session ON strength_history(session_id);
                """
            )
            # additive migration for pre-existing DBs
            cols = {r[1] for r in self._conn.execute("PRAGMA table_info(strength_history)").fetchall()}
            if "tier_distribution" not in cols:
                self._conn.execute("ALTER TABLE strength_history ADD COLUMN tier_distribution TEXT")
            if "learning_delta" not in cols:
                self._conn.execute("ALTER TABLE strength_history ADD COLUMN learning_delta REAL")
            self._conn.commit()

    # -- writes ------------------------------------------------------------

    def start_session(
        self,
        session_id: str,
        kind: str,
        model: str = "",
        concurrency: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO sessions (session_id, kind, model, started_at, concurrency, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, kind, model, _utc(), concurrency, json.dumps(metadata or {})),
            )
            self._conn.commit()
        return session_id

    def record_tokens(
        self,
        session_id: str,
        worker_id: str,
        role: str,
        model: str,
        usage: dict[str, Any],
        latency_s: float,
        ok: bool,
    ) -> None:
        details = (usage or {}).get("completion_tokens_details") or {}
        with self._lock:
            self._conn.execute(
                "INSERT INTO token_usage (session_id, worker_id, role, model, prompt_tokens, "
                "completion_tokens, reasoning_tokens, total_tokens, latency_s, ok, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    worker_id,
                    role,
                    model,
                    int((usage or {}).get("prompt_tokens", 0) or 0),
                    int((usage or {}).get("completion_tokens", 0) or 0),
                    int(details.get("reasoning_tokens", 0) or 0),
                    int((usage or {}).get("total_tokens", 0) or 0),
                    float(latency_s or 0.0),
                    1 if ok else 0,
                    _utc(),
                ),
            )
            self._conn.commit()

    def record_challenge(
        self,
        session_id: str,
        claim_id: str,
        primary_tier: str,
        validator_tier: str,
        tier_rank: dict[str, int],
    ) -> None:
        disagreed = 1 if primary_tier != validator_tier else 0
        more_skeptical = 1 if tier_rank.get(validator_tier, 9) > tier_rank.get(primary_tier, 9) else 0
        with self._lock:
            self._conn.execute(
                "INSERT INTO challenges (session_id, claim_id, primary_tier, validator_tier, "
                "disagreed, validator_more_skeptical, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, claim_id, primary_tier, validator_tier, disagreed, more_skeptical, _utc()),
            )
            self._conn.commit()

    def finish_session(
        self,
        session_id: str,
        workers_total: int,
        workers_ok: int,
        workers_failed: int,
        wall_seconds: float,
        effective_rps: float,
        ledger_entries: int,
        ledger_valid: bool,
        proof_hash: str,
        index: SwarmStrengthIndex,
        error_rate: float = 0.0,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET ended_at=?, workers_total=?, workers_ok=?, workers_failed=?, "
                "wall_seconds=?, effective_rps=?, ledger_entries=?, ledger_valid=?, proof_hash=?, "
                "strength_score=? WHERE session_id=?",
                (
                    _utc(), workers_total, workers_ok, workers_failed, wall_seconds, effective_rps,
                    ledger_entries, 1 if ledger_valid else 0, proof_hash, round(index.score, 4),
                    session_id,
                ),
            )
            self._conn.execute(
                "INSERT INTO strength_history (session_id, created_at, strength_score, grounded_ratio, "
                "evidence_ratio, challenge_rate, error_rate, tier_inflation_rate, tier_distribution, "
                "learning_delta) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id, _utc(), round(index.score, 4), round(index.grounding, 4),
                    round(index.evidence_quality, 4), round(index.challenge_activity, 4),
                    round(error_rate, 4), round(index.tier_inflation_rate, 4),
                    json.dumps(index.tier_distribution), index.learning_delta,
                ),
            )
            self._conn.commit()

    def previous_run(self, kind: str = "big_swarm") -> dict[str, Any] | None:
        """Most recent completed session of a kind (for reproducibility + delta)."""
        with self._lock:
            row = self._conn.execute(
                "SELECT s.session_id, s.strength_score, h.tier_distribution, s.ended_at "
                "FROM sessions s LEFT JOIN strength_history h ON h.session_id = s.session_id "
                "WHERE s.kind = ? AND s.ended_at IS NOT NULL ORDER BY s.ended_at DESC LIMIT 1",
                (kind,),
            ).fetchone()
        if not row:
            return None
        dist = None
        if row["tier_distribution"]:
            try:
                dist = json.loads(row["tier_distribution"])
            except (json.JSONDecodeError, TypeError):
                dist = None
        return {"session_id": row["session_id"], "index": row["strength_score"], "distribution": dist}

    # -- reads -------------------------------------------------------------

    def session_totals(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) n, SUM(total_tokens) total, SUM(prompt_tokens) prompt, "
                "SUM(completion_tokens) completion, SUM(reasoning_tokens) reasoning, "
                "AVG(latency_s) avg_latency FROM token_usage WHERE session_id=?",
                (session_id,),
            ).fetchone()
            ch = self._conn.execute(
                "SELECT COUNT(*) n, SUM(disagreed) disagreed, SUM(validator_more_skeptical) skeptical "
                "FROM challenges WHERE session_id=?",
                (session_id,),
            ).fetchone()
        return {
            "calls": row["n"] or 0,
            "total_tokens": row["total"] or 0,
            "prompt_tokens": row["prompt"] or 0,
            "completion_tokens": row["completion"] or 0,
            "reasoning_tokens": row["reasoning"] or 0,
            "avg_latency_s": round(row["avg_latency"] or 0.0, 3),
            "challenges": ch["n"] or 0,
            "challenged": ch["disagreed"] or 0,
            "validator_downgrades": ch["skeptical"] or 0,
        }

    def trend(self, kind: str = "big_swarm", limit: int = 20) -> dict[str, Any]:
        """TSSI across the last N sessions of a kind — the 'getting stronger?' answer."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT s.session_id, s.ended_at, s.strength_score, s.workers_total, s.workers_ok, "
                "s.effective_rps, s.ledger_valid, "
                "h.grounded_ratio, h.evidence_ratio, h.challenge_rate, h.error_rate, "
                "h.tier_inflation_rate, h.tier_distribution, h.learning_delta "
                "FROM sessions s LEFT JOIN strength_history h ON h.session_id = s.session_id "
                "WHERE s.kind = ? AND s.strength_score IS NOT NULL "
                "ORDER BY s.ended_at DESC LIMIT ?",
                (kind, limit),
            ).fetchall()
        runs = [dict(r) for r in rows]
        delta = None
        if len(runs) >= 2 and runs[0]["strength_score"] is not None and runs[1]["strength_score"] is not None:
            delta = round(runs[0]["strength_score"] - runs[1]["strength_score"], 4)
        return {
            "kind": kind,
            "runs": runs,
            "latest": runs[0] if runs else None,
            "delta_vs_previous": delta,
            "points": [
                {"session_id": r["session_id"], "ended_at": r["ended_at"], "index": r["strength_score"]}
                for r in reversed(runs)
            ],
        }

    def all_session_totals(self, kind: str | None = None) -> dict[str, Any]:
        with self._lock:
            if kind:
                row = self._conn.execute(
                    "SELECT COUNT(*) n, SUM(workers_total) workers, SUM(workers_ok) ok, "
                    "AVG(strength_score) avg_strength FROM sessions WHERE kind=?", (kind,)
                ).fetchone()
            else:
                row = self._conn.execute(
                    "SELECT COUNT(*) n, SUM(workers_total) workers, SUM(workers_ok) ok, "
                    "AVG(strength_score) avg_strength FROM sessions"
                ).fetchone()
            tok = self._conn.execute("SELECT SUM(total_tokens) t FROM token_usage").fetchone()
        return {
            "sessions": row["n"] or 0,
            "workers": row["workers"] or 0,
            "workers_ok": row["ok"] or 0,
            "avg_strength": round(row["avg_strength"] or 0.0, 4),
            "total_tokens": tok["t"] or 0,
        }
