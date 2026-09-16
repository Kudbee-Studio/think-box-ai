"""KUDBEE — Worker Reputation System.

Workers should not all be weighted equally. Reputation is accumulated from
*demonstrated* behaviour recorded by the flight recorder and the challenge arena:

  evidence_discipline   how often the worker used defensible tiers
  validation_accuracy   how often its verdict matched the settled decision
  successful_challenges challenges that were upheld (validator was right)
  false_challenges      challenges later overturned
  calibration           how well confidence tracked correctness
  trap_detection        detection rate on adversarial probes

The composite reputation is a weighted mean of those, so future swarms can
weight workers by performance instead of treating all N identically.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB = "data/thinkboxmd/db/reputation.db"

# credit for tier discipline (same curve as the strength index)
TIER_CREDIT = {"EVIDENCE": 1.0, "INFERENCE": 0.6, "HYPOTHESIS": 0.3, "UNVERIFIED": 0.15}

REP_WEIGHTS = {
    "evidence_discipline": 0.26,
    "validation_accuracy": 0.24,
    "challenge_quality": 0.20,
    "calibration": 0.14,
    "trap_detection": 0.16,
}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Reputation:
    worker_id: str
    role: str = ""
    runs: int = 0
    calls: int = 0
    errors: int = 0
    evidence_discipline: float = 0.0
    validation_accuracy: float = 0.0
    successful_challenges: int = 0
    false_challenges: int = 0
    calibration: float = 0.0
    trap_detection: float = 0.0
    reputation: float = 0.0

    @property
    def challenge_quality(self) -> float:
        total = self.successful_challenges + self.false_challenges
        return (self.successful_challenges / total) if total else 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "role": self.role,
            "runs": self.runs,
            "calls": self.calls,
            "errors": self.errors,
            "evidence_discipline": round(self.evidence_discipline, 4),
            "validation_accuracy": round(self.validation_accuracy, 4),
            "successful_challenges": self.successful_challenges,
            "false_challenges": self.false_challenges,
            "challenge_quality": round(self.challenge_quality, 4),
            "calibration": round(self.calibration, 4),
            "trap_detection": round(self.trap_detection, 4),
            "reputation": round(self.reputation, 4),
        }


class ReputationLedger:
    """SQLite-backed reputation store, scored from recorded evidence."""

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
                CREATE TABLE IF NOT EXISTS worker_reputation (
                    worker_id TEXT PRIMARY KEY,
                    role TEXT,
                    runs INTEGER DEFAULT 0,
                    calls INTEGER DEFAULT 0,
                    errors INTEGER DEFAULT 0,
                    tier_credit_sum REAL DEFAULT 0,
                    tier_credit_n INTEGER DEFAULT 0,
                    validation_hits INTEGER DEFAULT 0,
                    validation_n INTEGER DEFAULT 0,
                    successful_challenges INTEGER DEFAULT 0,
                    false_challenges INTEGER DEFAULT 0,
                    calib_sum REAL DEFAULT 0,
                    calib_n INTEGER DEFAULT 0,
                    trap_detect INTEGER DEFAULT 0,
                    trap_n INTEGER DEFAULT 0,
                    reputation REAL DEFAULT 0,
                    updated_at TEXT
                );
                """
            )
            self._conn.commit()

    def _ensure(self, worker_id: str, role: str = "") -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO worker_reputation (worker_id, role, updated_at) VALUES (?,?,?)",
            (worker_id, role, _utc()),
        )

    def _recompute(self, worker_id: str) -> float:
        r = self._conn.execute(
            "SELECT * FROM worker_reputation WHERE worker_id=?", (worker_id,)
        ).fetchone()
        if not r:
            return 0.0
        disc = (r["tier_credit_sum"] / r["tier_credit_n"]) if r["tier_credit_n"] else 0.0
        acc = (r["validation_hits"] / r["validation_n"]) if r["validation_n"] else 0.5
        chal = (r["successful_challenges"] /
                (r["successful_challenges"] + r["false_challenges"])) \
            if (r["successful_challenges"] + r["false_challenges"]) else 0.5
        calib = (r["calib_sum"] / r["calib_n"]) if r["calib_n"] else 0.5
        trap = (r["trap_detect"] / r["trap_n"]) if r["trap_n"] else 0.5
        rep = (
            REP_WEIGHTS["evidence_discipline"] * disc
            + REP_WEIGHTS["validation_accuracy"] * acc
            + REP_WEIGHTS["challenge_quality"] * chal
            + REP_WEIGHTS["calibration"] * calib
            + REP_WEIGHTS["trap_detection"] * trap
        )
        self._conn.execute(
            "UPDATE worker_reputation SET reputation=?, updated_at=? WHERE worker_id=?",
            (round(rep, 6), _utc(), worker_id),
        )
        return rep

    # -- inputs ------------------------------------------------------------

    def observe_call(self, worker_id: str, role: str, tier: str, ok: bool, confidence: float = 0.5) -> None:
        """One worker call: contributes tier discipline and a calibration point."""
        with self._lock:
            self._ensure(worker_id, role)
            credit = TIER_CREDIT.get(tier, 0.0) if ok else 0.0
            # calibration: honest low tiers with low confidence are well-calibrated
            honest = 1.0 if (tier in ("UNVERIFIED", "HYPOTHESIS") and confidence <= 0.5) or \
                            (tier in ("EVIDENCE", "INFERENCE") and confidence >= 0.5) else 0.4
            self._conn.execute(
                "UPDATE worker_reputation SET role=COALESCE(NULLIF(?,''), role), calls=calls+1, "
                "errors=errors+?, tier_credit_sum=tier_credit_sum+?, tier_credit_n=tier_credit_n+1, "
                "calib_sum=calib_sum+?, calib_n=calib_n+1 WHERE worker_id=?",
                (role, 0 if ok else 1, credit, honest, worker_id),
            )
            self._recompute(worker_id)
            self._conn.commit()

    def observe_validation(self, worker_id: str, agreed: bool) -> None:
        with self._lock:
            self._ensure(worker_id)
            self._conn.execute(
                "UPDATE worker_reputation SET validation_hits=validation_hits+?, "
                "validation_n=validation_n+1 WHERE worker_id=?",
                (1 if agreed else 0, worker_id),
            )
            self._recompute(worker_id)
            self._conn.commit()

    def observe_challenge(self, worker_id: str, upheld: bool) -> None:
        with self._lock:
            self._ensure(worker_id)
            col = "successful_challenges" if upheld else "false_challenges"
            self._conn.execute(
                f"UPDATE worker_reputation SET {col}={col}+1 WHERE worker_id=?", (worker_id,)
            )
            self._recompute(worker_id)
            self._conn.commit()

    def observe_trap(self, worker_id: str, detected: bool) -> None:
        with self._lock:
            self._ensure(worker_id)
            self._conn.execute(
                "UPDATE worker_reputation SET trap_detect=trap_detect+?, trap_n=trap_n+1 WHERE worker_id=?",
                (1 if detected else 0, worker_id),
            )
            self._recompute(worker_id)
            self._conn.commit()

    def start_run(self, worker_ids: list[str], role: str = "") -> None:
        with self._lock:
            for w in worker_ids:
                self._ensure(w, role)
                self._conn.execute(
                    "UPDATE worker_reputation SET runs=runs+1 WHERE worker_id=?", (w,)
                )
            self._conn.commit()

    # -- reads -------------------------------------------------------------

    def get(self, worker_id: str) -> dict[str, Any]:
        with self._lock:
            r = self._conn.execute(
                "SELECT * FROM worker_reputation WHERE worker_id=?", (worker_id,)
            ).fetchone()
        if not r:
            return {}
        d = dict(r)
        total_ch = d["successful_challenges"] + d["false_challenges"]
        d["challenge_quality"] = round(d["successful_challenges"] / total_ch, 4) if total_ch else 0.5
        d["evidence_discipline"] = round(d["tier_credit_sum"] / d["tier_credit_n"], 4) if d["tier_credit_n"] else 0.0
        d["validation_accuracy"] = round(d["validation_hits"] / d["validation_n"], 4) if d["validation_n"] else 0.5
        return d

    def leaderboard(self, limit: int = 25) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT worker_id, role, runs, calls, errors, reputation FROM worker_reputation "
                "WHERE calls > 0 ORDER BY reputation DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def summary(self) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) n, AVG(reputation) avg_rep, MAX(reputation) best, "
                "SUM(calls) calls, SUM(errors) errs FROM worker_reputation WHERE calls>0"
            ).fetchone()
        return {
            "workers": row["n"] or 0,
            "avg_reputation": round(row["avg_rep"] or 0.0, 4),
            "best_reputation": round(row["best"] or 0.0, 4),
            "total_calls": row["calls"] or 0,
            "total_errors": row["errs"] or 0,
        }

    def weights(self, worker_ids: list[str]) -> dict[str, float]:
        """Normalised reputation weights for future swarm sampling."""
        reps = {w: (self.get(w).get("reputation") or 0.5) for w in worker_ids}
        total = sum(reps.values()) or 1.0
        return {w: round(v / total, 6) for w, v in reps.items()}
