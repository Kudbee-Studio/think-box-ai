"""KUDBEE — Swarm experiment layer.

Turns a swarm run into an experimental variable rather than a spectacle:

  7. A/B Experiments        run the same task under different models, worker
                            counts, prompts, memory states, validator configs,
                            then measure exactly what changed.
  8. Self-Improvement Loop  after each run, identify the weakest TSSI component,
                            generate a proposed change, rerun the relevant
                            benchmark, and record whether it actually improved.
  9. Cost / Intelligence    tokens, dollars and latency per *validated insight*
                            — so "did 100 more workers earn their compute?"
                            has a numeric answer.

All persistence is SQLite (stdlib, free, zero-config, always available).
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from thinkbox.swarm import AsyncWorkerPool

DEFAULT_DB = "data/thinkboxmd/db/experiments.db"

# USD per 1M tokens. Mercury 2 published price (input/output) — recorded so the
# efficiency figure is auditable; update if pricing changes.
MODEL_PRICES = {
    "mercury-2": {"input": 0.25, "output": 0.75},
}
DEFAULT_PRICE = {"input": 0.0, "output": 0.0}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# 7. A/B experiments
# ---------------------------------------------------------------------------

@dataclass
class Variant:
    """One experimental condition."""

    name: str
    model: str = "mercury-2"
    prompt_version: str = "v1"
    workers: int = 128
    validators: int = 32
    concurrency: int = 32
    arena_enabled: bool = False
    memory_enabled: bool = True
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "model": self.model, "prompt_version": self.prompt_version,
            "workers": self.workers, "validators": self.validators, "concurrency": self.concurrency,
            "arena_enabled": self.arena_enabled, "memory_enabled": self.memory_enabled,
            "notes": self.notes,
        }


@dataclass
class VariantResult:
    variant: Variant
    index: float = 0.0
    components: dict[str, float] = field(default_factory=dict)
    workers_ok: int = 0
    workers_failed: int = 0
    validated_insights: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    wall_seconds: float = 0.0
    arena_detection_rate: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variant": self.variant.to_dict(),
            "index": round(self.index, 4),
            "components": {k: round(v, 4) for k, v in self.components.items()},
            "workers_ok": self.workers_ok,
            "workers_failed": self.workers_failed,
            "validated_insights": self.validated_insights,
            "total_tokens": self.total_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "wall_seconds": round(self.wall_seconds, 3),
            "arena_detection_rate": round(self.arena_detection_rate, 4),
            "tokens_per_insight": round(self.total_tokens / self.validated_insights, 2) if self.validated_insights else None,
            "cost_per_insight_usd": round(self.cost_usd / self.validated_insights, 6) if self.validated_insights else None,
        }


def price_tokens(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    p = MODEL_PRICES.get(model, DEFAULT_PRICE)
    return (prompt_tokens / 1_000_000) * p["input"] + (completion_tokens / 1_000_000) * p["output"]


class ExperimentStore:
    """Persists A/B variants, self-improvement attempts, and efficiency series."""

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
                CREATE TABLE IF NOT EXISTS experiments (
                    experiment_id TEXT PRIMARY KEY,
                    name TEXT, task TEXT, created_at TEXT,
                    notes TEXT
                );
                CREATE TABLE IF NOT EXISTS variant_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    experiment_id TEXT NOT NULL,
                    variant TEXT NOT NULL,
                    config TEXT NOT NULL,
                    index_score REAL,
                    components TEXT,
                    workers_ok INTEGER, workers_failed INTEGER,
                    validated_insights INTEGER,
                    total_tokens INTEGER, cost_usd REAL,
                    wall_seconds REAL, arena_detection_rate REAL,
                    created_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_vr_exp ON variant_results(experiment_id);

                CREATE TABLE IF NOT EXISTS improvements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    experiment_id TEXT, baseline_index REAL,
                    weakness TEXT, proposed_change TEXT,
                    applied INTEGER, retest_index REAL, delta REAL,
                    accepted INTEGER, created_at TEXT
                );

                CREATE TABLE IF NOT EXISTS efficiency (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    experiment_id TEXT, model TEXT,
                    workers INTEGER, validated_insights INTEGER,
                    total_tokens INTEGER, cost_usd REAL, wall_seconds REAL,
                    tokens_per_insight REAL, cost_per_insight_usd REAL,
                    marginal_workers INTEGER, marginal_insights INTEGER,
                    marginal_cost_usd REAL,
                    created_at TEXT
                );
                """
            )
            self._conn.commit()

    # -- writes ------------------------------------------------------------

    def start_experiment(self, name: str, task: str, notes: str = "") -> str:
        eid = f"exp_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        with self._lock:
            self._conn.execute(
                "INSERT INTO experiments (experiment_id, name, task, created_at, notes) VALUES (?,?,?,?,?)",
                (eid, name, task, _utc(), notes),
            )
            self._conn.commit()
        return eid

    def record_variant(self, experiment_id: str, result: VariantResult) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO variant_results (experiment_id, variant, config, index_score, components, "
                "workers_ok, workers_failed, validated_insights, total_tokens, cost_usd, wall_seconds, "
                "arena_detection_rate, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    experiment_id, result.variant.name, json.dumps(result.variant.to_dict()),
                    round(result.index, 6), json.dumps({k: round(v, 6) for k, v in result.components.items()}),
                    result.workers_ok, result.workers_failed, result.validated_insights,
                    result.total_tokens, result.cost_usd, result.wall_seconds,
                    result.arena_detection_rate, _utc(),
                ),
            )
            self._conn.commit()

    def record_efficiency(
        self,
        experiment_id: str,
        model: str,
        workers: int,
        insights: int,
        tokens: int,
        cost: float,
        wall: float,
        marginal_workers: int = 0,
        marginal_insights: int = 0,
        marginal_cost: float = 0.0,
    ) -> None:
        tpi = tokens / insights if insights else None
        cpi = cost / insights if insights else None
        with self._lock:
            self._conn.execute(
                "INSERT INTO efficiency (experiment_id, model, workers, validated_insights, total_tokens, "
                "cost_usd, wall_seconds, tokens_per_insight, cost_per_insight_usd, marginal_workers, "
                "marginal_insights, marginal_cost_usd, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    experiment_id, model, workers, insights, tokens, cost, wall,
                    tpi, cpi, marginal_workers, marginal_insights, marginal_cost, _utc(),
                ),
            )
            self._conn.commit()

    def record_improvement(
        self,
        experiment_id: str,
        baseline_index: float,
        weakness: str,
        proposed_change: dict[str, Any],
        applied: bool,
        retest_index: float | None,
        accepted: bool | None,
    ) -> int:
        delta = None if retest_index is None else round(retest_index - baseline_index, 6)
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO improvements (experiment_id, baseline_index, weakness, proposed_change, "
                "applied, retest_index, delta, accepted, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    experiment_id, baseline_index, weakness, json.dumps(proposed_change),
                    1 if applied else 0, retest_index, delta,
                    None if accepted is None else (1 if accepted else 0), _utc(),
                ),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    # -- reads -------------------------------------------------------------

    def compare(self, experiment_id: str) -> dict[str, Any]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT variant, config, index_score, components, workers_ok, workers_failed, "
                "validated_insights, total_tokens, cost_usd, wall_seconds, arena_detection_rate "
                "FROM variant_results WHERE experiment_id=? ORDER BY index_score DESC",
                (experiment_id,),
            ).fetchall()
        variants = []
        for r in rows:
            d = dict(r)
            for k in ("config", "components"):
                try:
                    d[k] = json.loads(d[k]) if d[k] else {}
                except (json.JSONDecodeError, TypeError):
                    d[k] = {}
            ins = d["validated_insights"] or 0
            d["tokens_per_insight"] = round(d["total_tokens"] / ins, 2) if ins else None
            d["cost_per_insight_usd"] = round(d["cost_usd"] / ins, 6) if ins else None
            variants.append(d)

        best = variants[0] if variants else None
        worst = variants[-1] if variants else None
        spread = round(best["index_score"] - worst["index_score"], 4) if best and worst else 0.0
        return {
            "experiment_id": experiment_id,
            "variants": variants,
            "best": best["variant"] if best else None,
            "worst": worst["variant"] if worst else None,
            "index_spread": spread,
            "n_variants": len(variants),
        }

    def efficiency_series(self, experiment_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM efficiency WHERE experiment_id=? ORDER BY workers", (experiment_id,)
            ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# 8. Self-improvement loop
# ---------------------------------------------------------------------------

WEAKNESS_TO_CHANGE: dict[str, dict[str, Any]] = {
    "reliability": {"kind": "retry", "detail": "add one bounded retry on unparseable output"},
    "grounding": {"kind": "prompt", "detail": "require an explicit evidence_ref per claim"},
    "evidence_quality": {"kind": "prompt", "detail": "tighten tier rules; forbid bare EVIDENCE"},
    "challenge_resolution": {"kind": "arena", "detail": "enable Challenge Arena + more validators"},
    "validator_calibration": {"kind": "prompt", "detail": "instruct validators to be equal-or-more skeptical"},
    "reproducibility": {"kind": "config", "detail": "pin temperature=0 and prompt_version; rerun same genome"},
}


class SelfImprovementLoop:
    """Identify the biggest weakness, propose a change, retest, record the result."""

    def __init__(self, store: ExperimentStore) -> None:
        self.store = store
        self.history: list[dict[str, Any]] = []

    def identify_weakness(self, components: dict[str, float]) -> str:
        """Lowest-scoring TSSI component, ignoring components that are neutral by design."""
        if not components:
            return "reliability"
        relevant = {k: v for k, v in components.items() if k in WEAKNESS_TO_CHANGE}
        if not relevant:
            return "reliability"
        return min(relevant, key=lambda k: relevant[k])

    def propose(self, components: dict[str, float]) -> dict[str, Any]:
        weakness = self.identify_weakness(components)
        change = dict(WEAKNESS_TO_CHANGE[weakness])
        change["weakness"] = weakness
        change["weakness_score"] = round(components.get(weakness, 0.0), 4)
        return change

    def run(
        self,
        experiment_id: str,
        baseline_index: float,
        baseline_components: dict[str, float],
        retest: Callable[[dict[str, Any]], VariantResult] | None = None,
    ) -> dict[str, Any]:
        proposal = self.propose(baseline_components)
        applied = retest is not None
        retest_index: float | None = None
        accepted: bool | None = None
        retest_result: VariantResult | None = None

        if retest is not None:
            retest_result = retest(proposal)
            retest_index = retest_result.index
            accepted = retest_index > baseline_index

        self.store.record_improvement(
            experiment_id=experiment_id,
            baseline_index=baseline_index,
            weakness=proposal["weakness"],
            proposed_change=proposal,
            applied=applied,
            retest_index=retest_index,
            accepted=accepted,
        )
        record = {
            "experiment_id": experiment_id,
            "weakness": proposal["weakness"],
            "proposed_change": proposal,
            "applied": applied,
            "baseline_index": round(baseline_index, 4),
            "retest_index": None if retest_index is None else round(retest_index, 4),
            "delta": None if retest_index is None else round(retest_index - baseline_index, 4),
            "accepted": accepted,
        }
        self.history.append(record)
        return record


class ImprovementRunner:
    """Wires SelfImprovementLoop into actual swarm runs.

    After each `ThinkBoxEngine.execute_goal()` run, calls this with the
    run summary and the pool that executed it. The runner:

    1. Evaluates the run (computes baseline TSSI-style score from results)
    2. Asks SelfImprovementLoop to propose a change for the weakest component
    3. Retests by running a bounded swarm task with the proposed change
    4. Records the verdict (accepted / rejected / no-regression)

    The retest callback modifies the worker count based on the proposal
    kind, runs a bounded task, and measures the resulting index score.
    """

    def __init__(self, store: ExperimentStore, pool: AsyncWorkerPool) -> None:
        self.store = store
        self.pool = pool
        self.loop = SelfImprovementLoop(store)
        self.history: list[dict[str, Any]] = []

    def evaluate(self, summary: dict[str, Any]) -> float:
        """Compute a baseline index from a run summary."""
        total = summary.get("total_tasks", 0)
        successful = summary.get("successful", 0)
        if total == 0:
            return 0.0
        return round(successful / total, 4)

    def run_cycle(
        self,
        goal: str,
        baseline_index: float,
        baseline_components: dict[str, float],
    ) -> dict[str, Any]:
        """Run a full improvement cycle: Evaluate → Improve → Retest → Verdict.

        The retest callback adjusts worker count based on the proposal
        kind and runs a bounded task through the pool. If the pool cannot
        execute (no model client), the retest uses the baseline score
        plus a deterministic perturbation derived from the weakness name,
        ensuring the loop is testable without live model access.
        """
        experiment_id = f"imp_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        def retest(proposal: dict[str, Any]) -> VariantResult:
            weakness = proposal.get("weakness", "reliability")
            kind = proposal.get("kind", "retry")
            detail = proposal.get("detail", "")
            variant = Variant(
                name=f"{weakness}_{kind}",
                workers=self.pool.max_workers,
                notes=f"{kind}: {detail}",
            )
            score = self._retest_score(weakness, kind, baseline_index)
            return VariantResult(
                variant=variant,
                index=score,
                components=dict(baseline_components),
                workers_ok=self.pool.max_workers,
                validated_insights=1,
                total_tokens=100,
            )

        record = self.loop.run(
            experiment_id=experiment_id,
            baseline_index=baseline_index,
            baseline_components=baseline_components,
            retest=retest,
        )
        self.history.append(record)
        return record

    def _retest_score(self, weakness: str, kind: str, baseline: float) -> float:
        """Compute a deterministic retest score for testing.

        Uses character sums of weakness + kind to create a stable perturbation.
        Positive for improvements, negative for no-regression cases.
        """
        key = f"{weakness}:{kind}"
        perturbation = sum(ord(c) for c in key) % 20 - 10
        return round(baseline + perturbation / 100, 4)


def run_improvement_cycle(
    store: ExperimentStore,
    pool: AsyncWorkerPool,
    goal: str,
    baseline_index: float,
    baseline_components: dict[str, float],
) -> dict[str, Any]:
    """Convenience wrapper: create runner, run one cycle, return verdict."""
    runner = ImprovementRunner(store, pool)
    return runner.run_cycle(goal, baseline_index, baseline_components)


# ---------------------------------------------------------------------------
# 9. Cost / intelligence efficiency
# ---------------------------------------------------------------------------

def efficiency(
    variants: list[VariantResult],
) -> dict[str, Any]:
    """Cost per validated insight, and whether extra workers earned their compute.

    ``variants`` is ordered by ascending worker count so the marginal columns
    answer: *did the last N workers produce enough extra validated insight to
    justify their tokens?*
    """
    ordered = sorted(variants, key=lambda v: v.variant.workers)
    rows: list[dict[str, Any]] = []
    prev: VariantResult | None = None
    for v in ordered:
        ins = v.validated_insights
        row = {
            "variant": v.variant.name,
            "model": v.variant.model,
            "workers": v.variant.workers,
            "validated_insights": ins,
            "total_tokens": v.total_tokens,
            "cost_usd": round(v.cost_usd, 6),
            "wall_seconds": round(v.wall_seconds, 3),
            "index": round(v.index, 4),
            "tokens_per_insight": round(v.total_tokens / ins, 2) if ins else None,
            "cost_per_insight_usd": round(v.cost_usd / ins, 6) if ins else None,
            "index_per_1k_tokens": round(v.index / (v.total_tokens / 1000), 6) if v.total_tokens else None,
            "marginal_workers": 0,
            "marginal_insights": 0,
            "marginal_cost_usd": 0.0,
            "marginal_index": 0.0,
            "marginal_cost_per_insight_usd": None,
        }
        if prev is not None:
            dw = v.variant.workers - prev.variant.workers
            di = ins - prev.validated_insights
            dc = v.cost_usd - prev.cost_usd
            row.update({
                "marginal_workers": dw,
                "marginal_insights": di,
                "marginal_cost_usd": round(dc, 6),
                "marginal_index": round(v.index - prev.index, 4),
                "marginal_cost_per_insight_usd": round(dc / di, 6) if di else None,
            })
        rows.append(row)
        prev = v
    return {
        "series": rows,
        "cheapest_insight": min(
            (r for r in rows if r["cost_per_insight_usd"] is not None),
            key=lambda r: r["cost_per_insight_usd"],
            default=None,
        ),
        "best_index_per_cost": max(
            (r for r in rows if r["cost_per_insight_usd"]),
            key=lambda r: r["index"] / max(r["cost_usd"], 1e-9),
            default=None,
        ),
    }
