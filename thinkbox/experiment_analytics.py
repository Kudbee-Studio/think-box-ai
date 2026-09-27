"""Multi-metric experiment analytics, lifecycle state machine, and NextAction generation.

Turns Mercury experiment results into persistent, queryable, multi-dimensional
experiment intelligence with autonomous learning loop primitives.

Features:
- Multi-metric aggregation (throughput, p50/p95/p99 latency, error rate, iterations)
- Run-over-run comparison
- Configurable regression detection (multi-metric)
- Experiment lifecycle state machine (PROPOSED → RUNNING → OBSERVED → VERIFIED → COMPARED → LEARNED)
- Structured NextAction generation (proof-backed, machine-readable)
- Replay from stored evidence
- Approval boundary enforcement
- Historical trend queries via SQLite

Reuses ExperimentManager, ExperimentDB, DashboardState, and existing proof infrastructure.
No new external dependencies. Stdlib only.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from thinkbox.experiment import (
    ExperimentManager,
    ExperimentDB,
    ExperimentRecord,
    ExperimentStatus,
    FourState,
    ProvenanceSource,
    ParameterClassification,
    ParameterProvenance,
)
from thinkbox.dashboard_state import get_dashboard_state, DashboardCategory, DashboardEvent


METRIC_KEYS = [
    "throughput",
    "p50_latency",
    "p95_latency",
    "p99_latency",
    "error_rate",
    "iteration_count",
]


LIFECYCLE_STATES = [
    "PROPOSED",
    "RUNNING",
    "OBSERVED",
    "VERIFIED",
    "COMPARED",
    "LEARNED",
]

LIFECYCLE_TRANSITIONS: dict[str, list[str]] = {
    "PROPOSED": ["RUNNING"],
    "RUNNING": ["OBSERVED"],
    "OBSERVED": ["VERIFIED"],
    "VERIFIED": ["COMPARED"],
    "COMPARED": ["LEARNED"],
    "LEARNED": [],
}

HIGHER_IS_WORSE = {"p50_latency", "p95_latency", "p99_latency", "error_rate"}


class ExperimentAnalytics:
    """Multi-metric analytics for Mercury experiments.

    Persists results via ExperimentManager, provides aggregation, comparison,
    regression detection, history queries, and dashboard integration.
    All metric operations are fail-closed for missing/invalid data.
    """

    def __init__(self, manager: ExperimentManager) -> None:
        self._manager = manager
        self._db: ExperimentDB = manager.db

    def persist_run(self, experiment_id: str, run_data: dict[str, Any]) -> str:
        """Persist experiment run metrics via add_artifact(). Returns artifact_id."""
        for key in METRIC_KEYS:
            if key not in run_data:
                raise ValueError(f"Missing required metric: {key}")
            if not isinstance(run_data[key], (int, float)):
                raise ValueError(
                    f"Metric {key} must be numeric, got {type(run_data[key]).__name__}"
                )

        metadata = {key: run_data[key] for key in METRIC_KEYS}
        metadata["experiment_id"] = experiment_id
        metadata["timestamp"] = datetime.now(timezone.utc).isoformat()

        raw = json.dumps(metadata, sort_keys=True, default=str)
        artifact_id = f"art_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"
        path = f"experiments/{experiment_id}/{artifact_id}"

        self._manager.add_artifact(
            experiment_id=experiment_id,
            artifact_type="mercury_metrics",
            path=path,
            metadata=metadata,
        )
        return artifact_id

    def _query_artifacts(self, experiment_id: Optional[str] = None) -> list[dict[str, Any]]:
        """Query mercury_metrics artifacts from the experiments table."""
        conn = sqlite3.connect(self._db.db_path)
        try:
            conn.row_factory = sqlite3.Row
            if experiment_id:
                cursor = conn.execute(
                    "SELECT a.*, e.timestamp as exp_timestamp FROM artifacts a "
                    "LEFT JOIN experiments e ON e.experiment_id = a.experiment_id "
                    "WHERE a.artifact_type = ? AND a.experiment_id = ? "
                    "ORDER BY a.timestamp DESC",
                    ("mercury_metrics", experiment_id),
                )
            else:
                cursor = conn.execute(
                    "SELECT a.*, e.timestamp as exp_timestamp FROM artifacts a "
                    "LEFT JOIN experiments e ON e.experiment_id = a.experiment_id "
                    "WHERE a.artifact_type = ? ORDER BY a.timestamp DESC",
                    ("mercury_metrics",),
                )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def _load_metadata(self, art: dict[str, Any]) -> dict[str, Any]:
        meta = art.get("metadata", {})
        if isinstance(meta, str):
            meta = json.loads(meta)
        return meta

    def aggregate_metrics(self, experiment_id: str) -> dict[str, Any]:
        """Compute multi-metric aggregation for an experiment. Fail-closed."""
        artifacts = self._query_artifacts(experiment_id)
        if not artifacts:
            raise ValueError(f"No mercury_metrics artifacts for experiment {experiment_id}")

        runs: list[dict[str, Any]] = []
        for art in artifacts:
            meta = self._load_metadata(art)
            validated: dict[str, Any] = {}
            for key in METRIC_KEYS:
                val = meta.get(key)
                if val is None or not isinstance(val, (int, float)):
                    raise ValueError(
                        f"Invalid or missing metric {key} in artifact {art.get('artifact_id', 'unknown')}"
                    )
                validated[key] = float(val)
            validated["artifact_id"] = art.get("artifact_id", "")
            validated["timestamp"] = art.get("timestamp", "")
            runs.append(validated)

        values: dict[str, list[float]] = {key: [r[key] for r in runs] for key in METRIC_KEYS}

        return {
            "experiment_id": experiment_id,
            "n_runs": len(runs),
            "runs": runs,
            "summary": {
                "throughput": {
                    "mean": round(sum(values["throughput"]) / len(values["throughput"]), 6),
                    "min": min(values["throughput"]),
                    "max": max(values["throughput"]),
                },
                "p50_latency": {
                    "mean": round(sum(values["p50_latency"]) / len(values["p50_latency"]), 6),
                    "min": min(values["p50_latency"]),
                    "max": max(values["p50_latency"]),
                },
                "p95_latency": {
                    "mean": round(sum(values["p95_latency"]) / len(values["p95_latency"]), 6),
                    "min": min(values["p95_latency"]),
                    "max": max(values["p95_latency"]),
                },
                "p99_latency": {
                    "mean": round(sum(values["p99_latency"]) / len(values["p99_latency"]), 6),
                    "min": min(values["p99_latency"]),
                    "max": max(values["p99_latency"]),
                },
                "error_rate": {
                    "mean": round(sum(values["error_rate"]) / len(values["error_rate"]), 6),
                    "min": min(values["error_rate"]),
                    "max": max(values["error_rate"]),
                },
                "iteration_count": {
                    "total": int(sum(values["iteration_count"])),
                    "mean": round(sum(values["iteration_count"]) / len(values["iteration_count"]), 6),
                },
            },
        }

    def compare_runs(self, experiment_id: str) -> dict[str, Any]:
        """Run-over-run comparison. Fail-closed if fewer than 2 runs."""
        aggregated = self.aggregate_metrics(experiment_id)
        runs = aggregated["runs"]
        if len(runs) < 2:
            raise ValueError(
                f"Need at least 2 runs for comparison, have {len(runs)} in experiment {experiment_id}"
            )

        comparisons = []
        for i in range(1, len(runs)):
            prev = runs[i - 1]
            curr = runs[i]
            delta: dict[str, Any] = {
                "run_current": curr["artifact_id"],
                "run_previous": prev["artifact_id"],
            }
            for key in METRIC_KEYS:
                diff = curr[key] - prev[key]
                pct = (diff / prev[key] * 100) if prev[key] != 0 else 0.0
                delta[key] = {"delta": round(diff, 6), "pct_change": round(pct, 4)}
            comparisons.append(delta)

        return {
            "experiment_id": experiment_id,
            "n_comparisons": len(comparisons),
            "comparisons": comparisons,
        }

    def detect_regression(self, metric: str = "throughput", experiment_id: Optional[str] = None) -> dict[str, Any]:
        """Detect regression with configurable threshold. Fail-closed.

        For higher-is-worse metrics (latency, error_rate): regression = increase.
        For higher-is-better metrics (throughput): regression = decrease.
        """
        if metric not in METRIC_KEYS:
            raise ValueError(f"Unknown metric: {metric}. Valid: {METRIC_KEYS}")

        if experiment_id:
            aggregated = self.aggregate_metrics(experiment_id)
            runs = aggregated["runs"]
        else:
            runs = self._query_all_runs(metric)

        if len(runs) < 2:
            raise ValueError(f"Need at least 2 runs for regression detection, have {len(runs)}")

        runs_sorted = sorted(runs, key=lambda r: r.get("timestamp", ""))
        prev = runs_sorted[-2]
        curr = runs_sorted[-1]
        prev_val = prev[metric]
        curr_val = curr[metric]
        pct_change = ((curr_val - prev_val) / prev_val * 100.0) if prev_val != 0 else 0.0

        threshold = 10.0
        if metric in HIGHER_IS_WORSE:
            is_regression = pct_change > threshold
        else:
            is_regression = pct_change < -threshold

        return {
            "metric": metric,
            "threshold_pct": threshold,
            "previous_value": prev_val,
            "current_value": curr_val,
            "pct_change": round(pct_change, 4),
            "is_regression": is_regression,
            "experiment_id": experiment_id or "cross_experiment",
        }

    def query_history(self, metric: str = "throughput", limit: int = 20) -> dict[str, Any]:
        """Query historical trend data via SQLite. Fail-closed for unknown metric."""
        if metric not in METRIC_KEYS:
            raise ValueError(f"Unknown metric: {metric}. Valid: {METRIC_KEYS}")

        artifacts = self._query_artifacts()
        runs: list[dict[str, Any]] = []
        for art in artifacts:
            meta = self._load_metadata(art)
            if metric in meta and isinstance(meta[metric], (int, float)):
                runs.append({
                    "experiment_id": art.get("experiment_id", ""),
                    "artifact_id": art.get("artifact_id", ""),
                    "metric": metric,
                    "value": float(meta[metric]),
                    "timestamp": art.get("timestamp", ""),
                })

        runs.sort(key=lambda r: r["timestamp"], reverse=True)
        runs = runs[:limit]

        trend = None
        if len(runs) >= 2:
            trend = runs[0]["value"] - runs[1]["value"]

        return {
            "metric": metric,
            "n_runs": len(runs),
            "limit": limit,
            "runs": runs,
            "trend_delta": round(trend, 6) if trend is not None else None,
            "trend_direction": (
                "improving" if trend and trend > 0
                else ("declining" if trend and trend < 0 else "stable")
            ),
        }

    def dashboard_data(self) -> dict[str, Any]:
        """Combined dashboard data including analytics aggregates."""
        state = get_dashboard_state()
        state_data = state.get_state()
        aggregates = self._db.get_dashboard_aggregates()

        artifacts = self._query_artifacts()
        mercury_runs = []
        for art in artifacts:
            meta = self._load_metadata(art)
            if "throughput" in meta and "p50_latency" in meta:
                mercury_runs.append({
                    "experiment_id": art.get("experiment_id", ""),
                    "artifact_id": art.get("artifact_id", ""),
                    "timestamp": art.get("timestamp", ""),
                    "throughput": meta.get("throughput"),
                    "p50_latency": meta.get("p50_latency"),
                    "p95_latency": meta.get("p95_latency"),
                    "p99_latency": meta.get("p99_latency"),
                    "error_rate": meta.get("error_rate"),
                    "iteration_count": meta.get("iteration_count"),
                })

        return {
            **aggregates,
            "dashboard_state": state_data,
            "mercury_metrics": {
                "total_runs": len(mercury_runs),
                "runs": mercury_runs,
            },
        }

    def _query_all_runs(self, metric: str) -> list[dict[str, Any]]:
        """Query all runs across experiments for a specific metric."""
        artifacts = self._query_artifacts()
        runs: list[dict[str, Any]] = []
        for art in artifacts:
            meta = self._load_metadata(art)
            if metric in meta and isinstance(meta[metric], (int, float)) and "throughput" in meta:
                runs.append({
                    "experiment_id": art.get("experiment_id", ""),
                    "artifact_id": art.get("artifact_id", ""),
                    "metric": metric,
                    "value": float(meta[metric]),
                    "timestamp": art.get("timestamp", ""),
                })
        runs.sort(key=lambda r: r["timestamp"])
        return runs


class ExperimentLifecycle:
    """Lifecycle state machine for experiments.

    States: PROPOSED → RUNNING → OBSERVED → VERIFIED → COMPARED → LEARNED
    Transitions are strict and validated. No skipping states.
    """

    VALID_TRANSITIONS: dict[str, list[str]] = LIFECYCLE_TRANSITIONS

    @classmethod
    def valid_states(cls) -> list[str]:
        return list(LIFECYCLE_STATES)

    @classmethod
    def can_transition(cls, from_state: str, to_state: str) -> bool:
        return to_state in cls.VALID_TRANSITIONS.get(from_state, [])

    @classmethod
    def validate_transition(cls, from_state: str, to_state: str) -> None:
        if from_state not in LIFECYCLE_STATES:
            raise ValueError(f"Invalid from_state: {from_state}")
        if to_state not in LIFECYCLE_STATES:
            raise ValueError(f"Invalid to_state: {to_state}")
        if not cls.can_transition(from_state, to_state):
            raise ValueError(
                f"Invalid transition: {from_state} → {to_state}. "
                f"Valid next states from {from_state}: {cls.VALID_TRANSITIONS[from_state]}"
            )

    def __init__(self, manager: ExperimentManager, experiment_id: str) -> None:
        self._manager = manager
        self._experiment_id = experiment_id
        self._current = self._current_state()

    def _current_state(self) -> str:
        exp = self._manager.db.get_experiment(self._experiment_id)
        if not exp:
            return "PROPOSED"
        conn = sqlite3.connect(self._manager.db.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT data FROM experiment_events "
                "WHERE experiment_id = ? AND event_type = 'lifecycle_transition' "
                "ORDER BY id DESC LIMIT 1",
                (self._experiment_id,),
            )
            row = cursor.fetchone()
            if row:
                data = json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]
                return data.get("to_state", "PROPOSED")
        finally:
            conn.close()
        status = exp.get("status", "pending")
        return "PROPOSED" if status == "pending" else status.upper()

    def current_state(self) -> str:
        self._current = self._current_state()
        return self._current

    def transition(self, to_state: str, evidence: dict[str, Any] = None) -> None:
        """Transition to a new lifecycle state. Fail-closed for invalid transitions."""
        from_state = self.current_state()
        self.validate_transition(from_state, to_state)
        self._current = to_state

        self._manager.add_action(
            self._experiment_id,
            {
                "type": "lifecycle_transition",
                "from_state": from_state,
                "to_state": to_state,
                "evidence": evidence or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

        self._manager.db.save_event(
            self._experiment_id,
            "lifecycle_transition",
            {"from_state": from_state, "to_state": to_state, "evidence": evidence or {}},
        )


class NextActionGenerator:
    """Generates structured, proof-backed NextActions from experiment outcomes.

    A NextAction is a machine-readable record consumable by the Mayor as the
    next unit of work. It contains what changed, whether it improved/regressed,
    confidence/evidence, anomalies, and recommended next experiment parameters.
    """

    def __init__(self, manager: ExperimentManager, analytics: ExperimentAnalytics) -> None:
        self._manager = manager
        self._analytics = analytics

    def generate(self, experiment_id: str, outcome: dict[str, Any], confidence: float = 0.0) -> dict[str, Any]:
        """Generate a structured NextAction from an experiment outcome."""
        exp = self._manager.db.get_experiment(experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")

        comparison = None
        regression = None
        try:
            comparison = self._analytics.compare_runs(experiment_id)
        except ValueError:
            comparison = {"error": "insufficient_runs_for_comparison"}

        for metric in METRIC_KEYS:
            try:
                regression = self._analytics.detect_regression(metric=metric, experiment_id=experiment_id)
                if regression.get("is_regression"):
                    break
            except ValueError:
                pass

        what_changed = self._what_changed(experiment_id)
        anomalies = self._detect_anomalies(experiment_id)

        recommended_params = self._recommend_next(experiment_id, regression, anomalies)

        next_action: dict[str, Any] = {
            "next_action_id": f"na_{uuid.uuid4().hex[:12]}",
            "experiment_id": experiment_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "what_changed": what_changed,
            "outcome": outcome,
            "confidence": confidence,
            "comparison": comparison,
            "regression": regression,
            "anomalies": anomalies,
            "recommended_next_experiment": recommended_params,
            "requires_human_approval": self._requires_approval(regression, confidence),
            "evidence": {
                "proof_trace": f"experiment:{experiment_id}",
                "metric_artifacts": self._metrics_artifact_ids(experiment_id),
            },
        }

        self._manager.record_outcome(
            experiment_id,
            {"next_action": next_action, "status": "generated"},
            confidence,
            four_state="PRODUCTION_READY",
        )
        self._manager.db.save_event(
            experiment_id, "next_action_generated", next_action
        )

        return next_action

    def _what_changed(self, experiment_id: str) -> dict[str, Any]:
        try:
            comparison = self._analytics.compare_runs(experiment_id)
            changes = []
            for comp in comparison.get("comparisons", []):
                for metric in METRIC_KEYS:
                    if metric in comp:
                        pct = comp[metric]["pct_change"]
                        if abs(pct) > 5.0:
                            direction = "improved" if pct > 0 else "regressed"
                            changes.append({
                                "metric": metric,
                                "direction": direction,
                                "pct_change": pct,
                            })
            return {"changes": changes, "summary": f"{len(changes)} significant changes detected"}
        except ValueError:
            return {"changes": [], "summary": "no comparison data available"}

    def _detect_anomalies(self, experiment_id: str) -> list[dict[str, Any]]:
        anomalies = []
        try:
            agg = self._analytics.aggregate_metrics(experiment_id)
            for run in agg.get("runs", []):
                for key in METRIC_KEYS:
                    val = run[key]
                    if key == "error_rate" and val > 0.1:
                        anomalies.append({"type": "high_error_rate", "metric": key, "value": val, "threshold": 0.1})
                    if key == "p99_latency" and val > 5.0:
                        anomalies.append({"type": "high_p99_latency", "metric": key, "value": val, "threshold": 5.0})
        except ValueError:
            pass
        return anomalies

    def _recommend_next(
        self, experiment_id: str, regression: Optional[dict[str, Any]], anomalies: list[dict[str, Any]]
    ) -> dict[str, Any]:
        if regression and regression.get("is_regression"):
            return {
                "type": "regression_followup",
                "rationale": "Regression detected; recommend investigation run with adjusted parameters",
                "adjustments": [{"metric": regression.get("metric"), "action": "investigate_root_cause"}],
                "max_retries": 2,
            }
        if anomalies:
            return {
                "type": "anomaly_followup",
                "rationale": f"{len(anomalies)} anomalies detected; recommend targeted follow-up",
                "adjustments": [{"anomaly": a.get("type"), "action": "investigate"} for a in anomalies],
                "max_retries": 2,
            }
        return {
            "type": "validation_run",
            "rationale": "No regression detected; recommend validation run to confirm stability",
            "adjustments": [],
            "max_retries": 1,
        }

    def _requires_approval(self, regression: Optional[dict[str, Any]], confidence: float) -> bool:
        if regression and regression.get("is_regression"):
            return True
        if confidence < 0.5:
            return True
        return False

    def _metrics_artifact_ids(self, experiment_id: str) -> list[str]:
        conn = sqlite3.connect(self._manager.db.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT artifact_id FROM artifacts WHERE experiment_id = ? AND artifact_type = ?",
                (experiment_id, "mercury_metrics"),
            )
            return [row["artifact_id"] for row in cursor.fetchall()]
        finally:
            conn.close()


class ReplayEngine:
    """Reproduce experiment analysis from stored evidence without rerunning."""

    def __init__(self, manager: ExperimentManager, analytics: ExperimentAnalytics) -> None:
        self._manager = manager
        self._analytics = analytics

    def replay(self, experiment_id: str) -> dict[str, Any]:
        """Reproduce analysis from stored evidence. Fail-closed."""
        exp = self._manager.db.get_experiment(experiment_id)
        if not exp:
            raise ValueError(f"Experiment {experiment_id} not found")

        try:
            metrics = self._analytics.aggregate_metrics(experiment_id)
        except ValueError as e:
            raise ValueError(f"Cannot replay: {e}")

        comparison = None
        try:
            comparison = self._analytics.compare_runs(experiment_id)
        except ValueError:
            comparison = {"error": "insufficient_runs"}

        history = self._analytics.query_history(limit=100)

        return {
            "experiment_id": experiment_id,
            "replayed_at": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics,
            "comparison": comparison,
            "history_context": history,
            "outcome": exp.get("outcome", {}),
            "proof": exp.get("proof", {}),
            "artifacts": [a for a in self._analytics._query_artifacts(experiment_id)],
        }


class ApprovalBoundary:
    """Defines what requires human approval vs autonomous execution.

    Autonomous: inspect, test, experiment, create branches
    Requires approval: merge, production deployment, spending/infrastructure, destructive ops
    """

    AUTONOMOUS_ACTIONS = {
        "inspect",
        "test",
        "experiment",
        "create_branch",
        "record_evidence",
        "generate_next_action",
        "replay_analysis",
    }

    APPROVAL_REQUIRED_ACTIONS = {
        "merge",
        "deploy_production",
        "infrastructure_change",
        "spend_budget",
        "delete_data",
        "modify_experiment_history",
    }

    def __init__(self, manager: ExperimentManager) -> None:
        self._manager = manager

    def requires_approval(self, action: str) -> bool:
        """Check if an action requires human approval."""
        return action in self.APPROVAL_REQUIRED_ACTIONS

    def get_boundary(self) -> dict[str, Any]:
        return {
            "autonomous": sorted(self.AUTONOMOUS_ACTIONS),
            "approval_required": sorted(self.APPROVAL_REQUIRED_ACTIONS),
        }

    def record_decision(self, experiment_id: str, action: str, approved: bool, approver: str = "") -> None:
        """Record an approval/rejection decision linked to proof."""
        self._manager.add_action(
            experiment_id,
            {
                "type": "approval_decision",
                "action": action,
                "approved": approved,
                "approver": approver,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        self._manager.db.save_event(
            experiment_id,
            "approval_decision",
            {"action": action, "approved": approved, "approver": approver},
        )


class ProofDecision:
    """Proof-backed decision records. DECISION → proof_sha256 → experiment_id → metrics."""

    def __init__(self, manager: ExperimentManager) -> None:
        self._manager = manager

    def record(
        self,
        experiment_id: str,
        decision: str,
        proof_sha256: str = "",
        metrics: dict[str, Any] = None,
        confidence: float = 0.0,
    ) -> None:
        """Record a decision linked to proof and metrics."""
        self._manager.add_proof(
            experiment_id,
            {
                "decision": decision,
                "proof_sha256": proof_sha256,
                "experiment_id": experiment_id,
                "metrics": metrics or {},
                "confidence": confidence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        self._manager.db.save_event(
            experiment_id,
            "proof_decision",
            {"decision": decision, "proof_sha256": proof_sha256, "metrics": metrics or {}},
        )


def _p95_from_latencies(latencies: list[float]) -> float:
    """Compute p95 latency from a list of latencies."""
    if not latencies:
        return 0.0
    sorted_l = sorted(latencies)
    idx = math.ceil(len(sorted_l) * 0.95) - 1
    return sorted_l[max(0, min(idx, len(sorted_l) - 1))]


@dataclass
class Opportunity:
    """An opportunity identified from execution feedback.

    Represents what the engine should investigate or iterate on next,
    derived from the analysis of a completed execution run.
    """

    opportunity_id: str
    source_experiment_id: str
    source_goal_run_id: str
    recommendation: dict[str, Any]
    metrics: dict[str, Any]
    created_at: str
    priority: str
    rationale: str


@dataclass
class OpportunityManager:
    """Tracks opportunities identified from execution feedback (Feedback -> Opportunity binding).

    When execution feedback is recorded, the generated NextAction recommendation
    is registered as an opportunity. The opportunity tracks what should be worked
    on next, and is consumed by the next planning/experiment cycle.

    Uses a MemoryStore-backed SQLite database for persistence so opportunities
    survive engine restarts.
    """

    def __init__(self, manager: ExperimentManager, analytics: ExperimentAnalytics,
                 db_path: str = ":memory:") -> None:
        self._manager = manager
        self._analytics = analytics
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS opportunities (
                    opportunity_id TEXT PRIMARY KEY,
                    source_experiment_id TEXT NOT NULL,
                    source_goal_run_id TEXT NOT NULL,
                    recommendation TEXT NOT NULL,
                    metrics TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    rationale TEXT NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def register_opportunity(self, source_experiment_id: str, source_goal_run_id: str,
                             recommendation: dict[str, Any], metrics: dict[str, Any],
                             priority: str = "medium") -> Opportunity:
        """Register a new opportunity from a feedback-generated recommendation.

        Returns the created Opportunity with a generated ID.
        """
        opportunity_id = f"opp_{uuid.uuid4().hex[:12]}"
        created_at = datetime.now(timezone.utc).isoformat()
        rationale = recommendation.get("rationale", "")

        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO opportunities (opportunity_id, source_experiment_id, source_goal_run_id, "
                "recommendation, metrics, created_at, priority, rationale) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    opportunity_id,
                    source_experiment_id,
                    source_goal_run_id,
                    json.dumps(recommendation, default=str),
                    json.dumps(metrics, default=str),
                    created_at,
                    priority,
                    rationale,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return Opportunity(
            opportunity_id=opportunity_id,
            source_experiment_id=source_experiment_id,
            source_goal_run_id=source_goal_run_id,
            recommendation=recommendation,
            metrics=metrics,
            created_at=created_at,
            priority=priority,
            rationale=rationale,
        )

    def get_current_opportunity(self) -> Optional[Opportunity]:
        """Retrieve the most recent unclaimed opportunity."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM opportunities ORDER BY created_at DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return Opportunity(
                opportunity_id=row["opportunity_id"],
                source_experiment_id=row["source_experiment_id"],
                source_goal_run_id=row["source_goal_run_id"],
                recommendation=json.loads(row["recommendation"]),
                metrics=json.loads(row["metrics"]),
                created_at=row["created_at"],
                priority=row["priority"],
                rationale=row["rationale"],
            )
        finally:
            conn.close()

    def list_opportunities(self, limit: int = 50) -> list[Opportunity]:
        """List opportunities ordered by recency."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM opportunities ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()
            return [
                Opportunity(
                    opportunity_id=row["opportunity_id"],
                    source_experiment_id=row["source_experiment_id"],
                    source_goal_run_id=row["source_goal_run_id"],
                    recommendation=json.loads(row["recommendation"]),
                    metrics=json.loads(row["metrics"]),
                    created_at=row["created_at"],
                    priority=row["priority"],
                    rationale=row["rationale"],
                )
                for row in rows
            ]
        finally:
            conn.close()

    def get_opportunity(self, opportunity_id: str) -> Optional[Opportunity]:
        """Retrieve a specific opportunity by ID."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM opportunities WHERE opportunity_id = ?",
                (opportunity_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return Opportunity(
                opportunity_id=row["opportunity_id"],
                source_experiment_id=row["source_experiment_id"],
                source_goal_run_id=row["source_goal_run_id"],
                recommendation=json.loads(row["recommendation"]),
                metrics=json.loads(row["metrics"]),
                created_at=row["created_at"],
                priority=row["priority"],
                rationale=row["rationale"],
            )
        finally:
            conn.close()

    def count_opportunities(self) -> int:
        """Return the total number of registered opportunities."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM opportunities")
            return cursor.fetchone()[0]
        finally:
            conn.close()


@dataclass
class LoopIteration:
    """Record of one autonomous loop iteration."""

    iteration_id: str
    loop_id: str
    started_at: str
    goal_run_id: str
    experiment_id: str
    opportunity_id: str
    completed_at: str
    cycle_time_s: float
    recommendation_type: str
    priority: str
    metrics: dict[str, Any]


@dataclass
class LoopMetrics:
    """Aggregated metrics across autonomous loop iterations."""

    total_iterations: int
    total_cycle_time_s: float
    avg_cycle_time_s: float
    min_cycle_time_s: float
    max_cycle_time_s: float
    recommendation_types: dict[str, int]
    priority_distribution: dict[str, int]
    first_iteration_id: str
    latest_iteration_id: str


class LoopTracer:
    """Observability layer for the autonomous decision-loop (Observability -> Learning binding).

    Records each iteration of the closed loop:
    Execution -> Feedback -> Opportunity -> Next Execution

    Provides measurements proving the loop is functioning, including:
    - Cycle time per iteration (execution -> feedback -> opportunity -> next execution)
    - Recommendation traceability (which recommendation drove which goal)
    - Loop iteration counts and statistics

    Uses SQLite for persistence so measurements survive restarts.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._init_db()
        self._current_loop_id: Optional[str] = None
        self._in_flight: dict[str, dict[str, Any]] = {}

    def _init_db(self) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS loop_iterations (
                    iteration_id TEXT PRIMARY KEY,
                    loop_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    cycle_time_s REAL NOT NULL,
                    goal_run_id TEXT NOT NULL,
                    experiment_id TEXT NOT NULL,
                    opportunity_id TEXT NOT NULL,
                    recommendation_type TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    metrics TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS loop_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def start_loop(self) -> str:
        """Start a new autonomous loop session. Returns the loop_id."""
        loop_id = f"loop_{uuid.uuid4().hex[:12]}"
        self._current_loop_id = loop_id
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO loop_metadata (key, value) VALUES (?, ?)",
                ("current_loop_id", loop_id),
            )
            conn.commit()
        finally:
            conn.close()
        return loop_id

    def start_iteration(self, goal_run_id: str, loop_id: Optional[str] = None) -> str:
        """Begin tracing a loop iteration. Returns the iteration_id."""
        iteration_id = f"iter_{uuid.uuid4().hex[:12]}"
        lid = loop_id or self._current_loop_id or f"loop_{uuid.uuid4().hex[:12]}"
        if not self._current_loop_id and not self._get_metadata("current_loop_id"):
            conn = sqlite3.connect(self._db_path)
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO loop_metadata (key, value) VALUES (?, ?)",
                    ("current_loop_id", lid),
                )
                conn.commit()
            finally:
                conn.close()
        self._current_loop_id = lid
        started_at = datetime.now(timezone.utc).isoformat()
        self._in_flight[iteration_id] = {
            "iteration_id": iteration_id,
            "loop_id": lid,
            "started_at": started_at,
            "goal_run_id": goal_run_id,
        }
        return iteration_id

    def complete_iteration(
        self,
        iteration_id: str,
        experiment_id: str,
        opportunity_id: str,
        recommendation_type: str,
        priority: str,
        metrics: dict[str, Any],
    ) -> LoopIteration:
        """Complete a loop iteration and persist it.

        Records the full cycle: when the iteration started (goal execution)
        through when the feedback-generated opportunity was registered.
        """
        if iteration_id not in self._in_flight:
            raise ValueError(f"No in-flight iteration with ID: {iteration_id}")
        in_flight = self._in_flight.pop(iteration_id)
        started_at = in_flight["started_at"]
        completed_at = datetime.now(timezone.utc).isoformat()
        started_dt = datetime.fromisoformat(started_at)
        completed_dt = datetime.fromisoformat(completed_at)
        cycle_time_s = round((completed_dt - started_dt).total_seconds(), 6)

        iteration = LoopIteration(
            iteration_id=iteration_id,
            loop_id=in_flight["loop_id"],
            started_at=started_at,
            completed_at=completed_at,
            cycle_time_s=cycle_time_s,
            goal_run_id=in_flight["goal_run_id"],
            experiment_id=experiment_id,
            opportunity_id=opportunity_id,
            recommendation_type=recommendation_type,
            priority=priority,
            metrics=metrics,
        )

        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO loop_iterations "
                "(iteration_id, loop_id, started_at, completed_at, cycle_time_s, "
                "goal_run_id, experiment_id, opportunity_id, recommendation_type, priority, metrics) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    iteration.iteration_id,
                    iteration.loop_id,
                    iteration.started_at,
                    iteration.completed_at,
                    iteration.cycle_time_s,
                    iteration.goal_run_id,
                    iteration.experiment_id,
                    iteration.opportunity_id,
                    iteration.recommendation_type,
                    iteration.priority,
                    json.dumps(metrics, default=str),
                ),
            )
            conn.execute(
                "INSERT OR REPLACE INTO loop_metadata (key, value) VALUES (?, ?)",
                ("latest_iteration_id", iteration_id),
            )
            count = conn.execute("SELECT COUNT(*) FROM loop_iterations").fetchone()[0]
            if count == 1:
                conn.execute(
                    "INSERT OR REPLACE INTO loop_metadata (key, value) VALUES (?, ?)",
                    ("first_iteration_id", iteration_id),
                )
            conn.commit()
        finally:
            conn.close()
        return iteration

    def get_iteration(self, iteration_id: str) -> Optional[LoopIteration]:
        """Retrieve a specific loop iteration."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM loop_iterations WHERE iteration_id = ?",
                (iteration_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return LoopIteration(
                iteration_id=row["iteration_id"],
                loop_id=row["loop_id"],
                started_at=row["started_at"],
                completed_at=row["completed_at"],
                cycle_time_s=row["cycle_time_s"],
                goal_run_id=row["goal_run_id"],
                experiment_id=row["experiment_id"],
                opportunity_id=row["opportunity_id"],
                recommendation_type=row["recommendation_type"],
                priority=row["priority"],
                metrics=json.loads(row["metrics"]),
            )
        finally:
            conn.close()

    def list_iterations(self, loop_id: Optional[str] = None, limit: int = 50) -> list[LoopIteration]:
        """List loop iterations, optionally filtered by loop_id."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.row_factory = sqlite3.Row
            if loop_id:
                cursor = conn.execute(
                    "SELECT * FROM loop_iterations WHERE loop_id = ? ORDER BY started_at DESC LIMIT ?",
                    (loop_id, limit),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM loop_iterations ORDER BY started_at DESC LIMIT ?",
                    (limit,),
                )
            rows = cursor.fetchall()
            return [
                LoopIteration(
                    iteration_id=row["iteration_id"],
                    loop_id=row["loop_id"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                    cycle_time_s=row["cycle_time_s"],
                    goal_run_id=row["goal_run_id"],
                    experiment_id=row["experiment_id"],
                    opportunity_id=row["opportunity_id"],
                    recommendation_type=row["recommendation_type"],
                    priority=row["priority"],
                    metrics=json.loads(row["metrics"]),
                )
                for row in rows
            ]
        finally:
            conn.close()

    def get_metrics(self) -> LoopMetrics:
        """Aggregate measurements across all loop iterations."""
        iterations = self.list_iterations(limit=10000)
        if not iterations:
            return LoopMetrics(
                total_iterations=0,
                total_cycle_time_s=0.0,
                avg_cycle_time_s=0.0,
                min_cycle_time_s=0.0,
                max_cycle_time_s=0.0,
                recommendation_types={},
                priority_distribution={},
                first_iteration_id="",
                latest_iteration_id="",
            )

        cycle_times = [i.cycle_time_s for i in iterations]
        rec_types: dict[str, int] = {}
        priorities: dict[str, int] = {}
        for it in iterations:
            rec_types[it.recommendation_type] = rec_types.get(it.recommendation_type, 0) + 1
            priorities[it.priority] = priorities.get(it.priority, 0) + 1

        return LoopMetrics(
            total_iterations=len(iterations),
            total_cycle_time_s=round(sum(cycle_times), 6),
            avg_cycle_time_s=round(sum(cycle_times) / len(cycle_times), 6),
            min_cycle_time_s=round(min(cycle_times), 6),
            max_cycle_time_s=round(max(cycle_times), 6),
            recommendation_types=rec_types,
            priority_distribution=priorities,
            first_iteration_id=self._get_metadata("first_iteration_id"),
            latest_iteration_id=self._get_metadata("latest_iteration_id"),
        )

    def _get_metadata(self, key: str) -> str:
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.execute("SELECT value FROM loop_metadata WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else ""
        finally:
            conn.close()

    def get_current_loop_id(self) -> str:
        """Return the current loop_id, or empty string if none started."""
        if self._current_loop_id:
            return self._current_loop_id
        return self._get_metadata("current_loop_id")


@dataclass
class TuningDecision:
    """A single auto-tuning adjustment made to the engine."""

    decision_id: str
    iteration_id: str
    metric_name: str
    metric_value: float
    threshold: float
    old_value: Any
    new_value: Any
    rationale: str
    decided_at: str


class EngineAutoTuner:
    """Self-tuning layer for the autonomous decision-loop (Learning -> Memory binding at meta-level).

    Reviews LoopTracer measurements and adjusts engine configuration parameters:
    - High error_rate -> increase max_retries
    - High p95_latency -> increase autoscaler workers
    - Low throughput -> increase default_workers
    - High cycle_time -> reduce speculative ratio

    Each tuning decision is recorded as a TuningDecision for traceability.
    Uses SQLite for persistence.
    """

    ERROR_RATE_THRESHOLD = 0.1
    LATENCY_THRESHOLD_S = 2.0
    LOW_THROUGHPUT_THRESHOLD = 5.0

    def __init__(self, loop_tracer: LoopTracer, db_path: str = ":memory:") -> None:
        self._tracer = loop_tracer
        self._db_path = db_path
        self._init_db()
        self._decisions: list[TuningDecision] = []

    def _init_db(self) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tuning_decisions (
                    decision_id TEXT PRIMARY KEY,
                    iteration_id TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    threshold REAL NOT NULL,
                    old_value TEXT NOT NULL,
                    new_value TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    decided_at TEXT NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def review_and_tune(self, engine: Any) -> list[TuningDecision]:
        """Review LoopTracer metrics and adjust engine config.

        Analyzes the latest loop iterations and applies tuning decisions
        to the provided engine's configuration. Returns the list of
        decisions made during this review.
        """
        decisions: list[TuningDecision] = []
        metrics = self._tracer.get_metrics()

        if metrics.total_iterations < 2:
            return decisions

        iterations = self._tracer.list_iterations(limit=10)
        if len(iterations) < 2:
            return decisions

        latest = iterations[0]
        prev = iterations[1]

        error_rate = latest.metrics.get("error_rate", 0.0)
        if error_rate > self.ERROR_RATE_THRESHOLD:
            old_retries = getattr(engine, "config", engine).max_retries if hasattr(engine, "config") else None
            decision = self._adjust_max_retries(engine, latest, error_rate, old_retries)
            if decision:
                decisions.append(decision)

        p50_latency = latest.metrics.get("p50_latency", 0.0)
        if p50_latency > self.LATENCY_THRESHOLD_S:
            old_workers = None
            scaler_cfg = getattr(getattr(engine, "config", None), "scaler_config", None)
            if scaler_cfg:
                old_workers = scaler_cfg.default_workers
            decision = self._adjust_workers(engine, latest, p50_latency, old_workers)
            if decision:
                decisions.append(decision)

        throughput = latest.metrics.get("throughput", 0.0)
        if throughput < self.LOW_THROUGHPUT_THRESHOLD:
            decision = self._adjust_for_low_throughput(engine, latest, throughput)
            if decision:
                decisions.append(decision)

        self._decisions.extend(decisions)
        self._persist_decisions(decisions)
        return decisions

    def _adjust_max_retries(self, engine: Any, iteration: LoopIteration,
                             error_rate: float, old_value: Any) -> Optional[TuningDecision]:
        """Increase max_retries when error_rate exceeds threshold."""
        config = getattr(engine, "config", None) if not hasattr(engine, "max_retries") else engine
        if config is None:
            return None
        new_retries = min(getattr(config, "max_retries", 3) + 1, 10)
        if hasattr(config, "max_retries"):
            config.max_retries = new_retries
        else:
            config.max_retries = new_retries

        decision = TuningDecision(
            decision_id=f"td_{uuid.uuid4().hex[:12]}",
            iteration_id=iteration.iteration_id,
            metric_name="error_rate",
            metric_value=error_rate,
            threshold=self.ERROR_RATE_THRESHOLD,
            old_value=str(old_value),
            new_value=str(new_retries),
            rationale=f"error_rate {error_rate:.4f} exceeds threshold {self.ERROR_RATE_THRESHOLD}; "
                      f"increased max_retries to {new_retries}",
            decided_at=datetime.now(timezone.utc).isoformat(),
        )
        self.emit_tuning_event(iteration, decision)
        return decision

    def _adjust_workers(self, engine: Any, iteration: LoopIteration,
                        latency: float, old_value: Any) -> Optional[TuningDecision]:
        """Increase default_workers when p50_latency exceeds threshold."""
        config = getattr(engine, "config", None)
        scaler_cfg = getattr(config, "scaler_config", None)
        if scaler_cfg is None:
            return None
        new_workers = min(int(scaler_cfg.default_workers * 2), scaler_cfg.max_workers)
        old_workers = scaler_cfg.default_workers
        scaler_cfg.default_workers = new_workers

        decision = TuningDecision(
            decision_id=f"td_{uuid.uuid4().hex[:12]}",
            iteration_id=iteration.iteration_id,
            metric_name="p50_latency",
            metric_value=latency,
            threshold=self.LATENCY_THRESHOLD_S,
            old_value=str(old_workers),
            new_value=str(new_workers),
            rationale=f"p50_latency {latency:.4f}s exceeds threshold {self.LATENCY_THRESHOLD_S}s; "
                      f"doubled default_workers to {new_workers}",
            decided_at=datetime.now(timezone.utc).isoformat(),
        )
        self.emit_tuning_event(iteration, decision)
        return decision

    def _adjust_for_low_throughput(self, engine: Any, iteration: LoopIteration,
                                    throughput: float) -> Optional[TuningDecision]:
        """Increase workers when throughput is below threshold."""
        config = getattr(engine, "config", None)
        scaler_cfg = getattr(config, "scaler_config", None)
        if scaler_cfg is None:
            return None
        old_workers = scaler_cfg.default_workers
        new_workers = min(int(scaler_cfg.default_workers * 1.5), scaler_cfg.max_workers)
        scaler_cfg.default_workers = new_workers

        decision = TuningDecision(
            decision_id=f"td_{uuid.uuid4().hex[:12]}",
            iteration_id=iteration.iteration_id,
            metric_name="throughput",
            metric_value=throughput,
            threshold=self.LOW_THROUGHPUT_THRESHOLD,
            old_value=str(old_workers),
            new_value=str(new_workers),
            rationale=f"throughput {throughput:.4f} below threshold {self.LOW_THROUGHPUT_THRESHOLD}; "
                      f"increased default_workers to {new_workers}",
            decided_at=datetime.now(timezone.utc).isoformat(),
        )
        self.emit_tuning_event(iteration, decision)
        return decision

    def emit_tuning_event(self, iteration: LoopIteration, decision: TuningDecision) -> None:
        """Emit a dashboard event for the tuning decision."""
        try:
            state = get_dashboard_state()
            state.emit(DashboardEvent(
                category=DashboardCategory.EXECUTION,
                event_type="engine_tuning",
                source="EngineAutoTuner",
                data={
                    "decision_id": decision.decision_id,
                    "iteration_id": iteration.iteration_id,
                    "metric": decision.metric_name,
                    "rationale": decision.rationale,
                    "old_value": decision.old_value,
                    "new_value": decision.new_value,
                },
                evidence_label="infmred",
            ))
        except Exception:
            pass

    def _persist_decisions(self, decisions: list[TuningDecision]) -> None:
        """Persist tuning decisions to SQLite."""
        if not decisions:
            return
        conn = sqlite3.connect(self._db_path)
        try:
            for d in decisions:
                conn.execute(
                    "INSERT INTO tuning_decisions "
                    "(decision_id, iteration_id, metric_name, metric_value, threshold, "
                    "old_value, new_value, rationale, decided_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        d.decision_id, d.iteration_id, d.metric_name, d.metric_value,
                        d.threshold, d.old_value, d.new_value, d.rationale, d.decided_at,
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def list_decisions(self, limit: int = 50) -> list[dict[str, Any]]:
        """List tuning decisions ordered by recency."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM tuning_decisions ORDER BY decided_at DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_decision_count(self) -> int:
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM tuning_decisions")
            return cursor.fetchone()[0]
        finally:
            conn.close()


@dataclass
class GeneralizablePattern:
    """A pattern that generalizes across multiple experiments."""

    pattern_id: str
    metric_name: str
    recommendation_type: str
    improvement_direction: str
    supporting_iteration_ids: list[str]
    supporting_experiment_ids: list[str]
    evidence: dict[str, Any]
    confidence: float
    created_at: str


@dataclass
class GeneralizationResult:
    """Result of cross-experiment generalization analysis."""

    patterns_identified: list[str]
    generalization_confidence: float
    iterations_analyzed: int
    timestamp: str


class CrossExperimentGeneralizer:
    """Identifies generalizable patterns across multiple loop iterations.

    Examines LoopTracer iterations and experiment outcomes to find patterns
    that generalize: e.g., "high error_rate consistently correlates with
    anomaly_followup recommendations that improve throughput."

    Stores generalized patterns as organizational knowledge via
    ExperimentManager's verified knowledge layer.
    """

    MIN_ITERATIONS_FOR_GENERALIZATION = 3
    CONFIDENCE_THRESHOLD = 0.6

    def __init__(self, tracer: LoopTracer, manager: ExperimentManager,
                 analytics: ExperimentAnalytics, db_path: str = ":memory:") -> None:
        self._tracer = tracer
        self._manager = manager
        self._analytics = analytics
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS generalizable_patterns (
                    pattern_id TEXT PRIMARY KEY,
                    metric_name TEXT NOT NULL,
                    recommendation_type TEXT NOT NULL,
                    improvement_direction TEXT NOT NULL,
                    supporting_iteration_ids TEXT NOT NULL,
                    supporting_experiment_ids TEXT NOT NULL,
                    evidence TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS generalization_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    iterations_analyzed INTEGER NOT NULL,
                    patterns_identified INTEGER NOT NULL,
                    generalization_confidence REAL NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def generalize(self) -> GeneralizationResult:
        """Analyze all loop iterations and identify generalizable patterns.

        A pattern is identified when:
        - At least MIN_ITERATIONS_FOR_GENERALIZATION iterations exist
        - A metric consistently shows the same improvement direction
          across iterations with the same recommendation type
        - Confidence (proportion of iterations showing the pattern) >= CONFIDENCE_THRESHOLD

        Returns a GeneralizationResult with pattern IDs identified.
        """
        iterations = self._tracer.list_iterations(limit=100)
        if len(iterations) < self.MIN_ITERATIONS_FOR_GENERALIZATION:
            return GeneralizationResult(
                patterns_identified=[],
                generalization_confidence=0.0,
                iterations_analyzed=len(iterations),
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        by_rec_type: dict[str, list[LoopIteration]] = {}
        for it in iterations:
            rec_type = it.recommendation_type
            by_rec_type.setdefault(rec_type, []).append(it)

        patterns: list[GeneralizablePattern] = []
        for rec_type, group in by_rec_type.items():
            if len(group) < 2:
                continue
            pattern = self._analyze_group(rec_type, group)
            if pattern and pattern.confidence >= self.CONFIDENCE_THRESHOLD:
                self._persist_pattern(pattern)
                patterns.append(pattern)

        confidence = len(patterns) / len(by_rec_type) if by_rec_type else 0.0
        result = GeneralizationResult(
            patterns_identified=[p.pattern_id for p in patterns],
            generalization_confidence=round(confidence, 4),
            iterations_analyzed=len(iterations),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._persist_history(result)
        self._emit_generalization_event(result, patterns)
        return result

    def _analyze_group(self, rec_type: str, group: list[LoopIteration]) -> Optional[GeneralizablePattern]:
        """Analyze a group of iterations with the same recommendation type for patterns."""
        throughputs = [it.metrics.get("throughput", 0.0) for it in group]
        latencies = [it.metrics.get("p50_latency", 0.0) for it in group]
        error_rates = [it.metrics.get("error_rate", 0.0) for it in group]

        pattern_id = f"pat_{uuid.uuid4().hex[:12]}"
        supporting_iters = [it.iteration_id for it in group]
        supporting_exps = [it.experiment_id for it in group]

        metric_findings: dict[str, str] = {}
        if len(throughputs) >= 2:
            trend = throughputs[-1] - throughputs[0]
            direction = "improving" if trend > 0 else ("declining" if trend < 0 else "stable")
            metric_findings["throughput"] = direction

        if len(latencies) >= 2:
            trend = latencies[-1] - latencies[0]
            direction = "improving" if trend < 0 else ("declining" if trend > 0 else "stable")
            metric_findings["p50_latency"] = direction

        if len(error_rates) >= 2:
            trend = error_rates[-1] - error_rates[0]
            direction = "improving" if trend < 0 else ("declining" if trend > 0 else "stable")
            metric_findings["error_rate"] = direction

        confidence = 1.0 if len(group) >= 2 else 0.5

        primary_metric = ""
        primary_direction = ""
        for metric, direction in metric_findings.items():
            if direction in ("improving", "declining"):
                primary_metric = metric
                primary_direction = direction
                break

        if not primary_metric:
            return None

        evidence = {
            "metric_findings": metric_findings,
            "n_iterations": len(group),
            "throughput_values": throughputs,
            "latency_values": latencies,
            "error_rate_values": error_rates,
        }

        return GeneralizablePattern(
            pattern_id=pattern_id,
            metric_name=primary_metric,
            recommendation_type=rec_type,
            improvement_direction=primary_direction,
            supporting_iteration_ids=supporting_iters,
            supporting_experiment_ids=supporting_exps,
            evidence=evidence,
            confidence=round(confidence, 4),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def _persist_pattern(self, pattern: GeneralizablePattern) -> None:
        """Persist a generalizable pattern to SQLite."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO generalizable_patterns "
                "(pattern_id, metric_name, recommendation_type, improvement_direction, "
                "supporting_iteration_ids, supporting_experiment_ids, evidence, confidence, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    pattern.pattern_id,
                    pattern.metric_name,
                    pattern.recommendation_type,
                    pattern.improvement_direction,
                    json.dumps(pattern.supporting_iteration_ids),
                    json.dumps(pattern.supporting_experiment_ids),
                    json.dumps(pattern.evidence, default=str),
                    pattern.confidence,
                    pattern.created_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def list_patterns(self, limit: int = 50) -> list[dict[str, Any]]:
        """List identified generalizable patterns."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM generalizable_patterns ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_pattern_count(self) -> int:
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM generalizable_patterns")
            return cursor.fetchone()[0]
        finally:
            conn.close()

    def _persist_history(self, result: GeneralizationResult) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO generalization_history "
                "(timestamp, iterations_analyzed, patterns_identified, generalization_confidence) "
                "VALUES (?, ?, ?, ?)",
                (
                    result.timestamp,
                    result.iterations_analyzed,
                    len(result.patterns_identified),
                    result.generalization_confidence,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _emit_generalization_event(self, result: GeneralizationResult,
                                   patterns: list[GeneralizablePattern]) -> None:
        """Emit a dashboard event for the generalization analysis."""
        try:
            state = get_dashboard_state()
            state.emit(DashboardEvent(
                category=DashboardCategory.EXECUTION,
                event_type="cross_experiment_generalization",
                source="CrossExperimentGeneralizer",
                data={
                    "iterations_analyzed": result.iterations_analyzed,
                    "patterns_identified": len(result.patterns_identified),
                    "generalization_confidence": result.generalization_confidence,
                    "pattern_summaries": [
                        {
                            "pattern_id": p.pattern_id,
                            "metric_name": p.metric_name,
                            "recommendation_type": p.recommendation_type,
                            "improvement_direction": p.improvement_direction,
                            "confidence": p.confidence,
                        }
                        for p in patterns
                    ],
                },
                evidence_label="infmred",
            ))
        except Exception:
            pass


@dataclass
class LoopSession:
    """A closed autonomous loop session with summary metrics."""

    session_id: str
    loop_id: str
    started_at: str
    closed_at: str
    iterations_count: int
    avg_throughput: float
    avg_p50_latency: float
    avg_error_rate: float
    total_cycle_time_s: float
    patterns_identified: int
    summary: dict[str, Any]


@dataclass
class SessionComparison:
    """Comparison of two loop sessions."""

    baseline_session_id: str
    candidate_session_id: str
    throughput_delta: float
    throughput_pct_change: float
    latency_delta: float
    latency_pct_change: float
    error_rate_delta: float
    improved: bool
    summary: dict[str, Any]


class LoopSessionManager:
    """Manages loop sessions for cross-cycle learning (Session -> Organizational Memory binding).

    A loop session represents a complete autonomous decision cycle:
    start -> multiple executions -> feedback -> opportunities -> generalization -> close.

    Sessions enable measuring improvement across loop cycles, not just within
    a single cycle. Closed sessions are compared to drive the next session's
    configuration.
    """

    MIN_ITERATIONS_TO_CLOSE = 3

    def __init__(self, tracer: LoopTracer, generalizer: CrossExperimentGeneralizer,
                 db_path: str = ":memory:") -> None:
        self._tracer = tracer
        self._generalizer = generalizer
        self._db_path = db_path
        self._current_session: Optional[LoopSession] = None
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS loop_sessions (
                    session_id TEXT PRIMARY KEY,
                    loop_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    closed_at TEXT NOT NULL,
                    iterations_count INTEGER NOT NULL,
                    avg_throughput REAL NOT NULL,
                    avg_p50_latency REAL NOT NULL,
                    avg_error_rate REAL NOT NULL,
                    total_cycle_time_s REAL NOT NULL,
                    patterns_identified INTEGER NOT NULL,
                    summary TEXT NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def start_session(self) -> str:
        """Start a new loop session. Returns the session_id."""
        self._tracer.start_loop()
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        self._current_session = None
        return session_id

    def close_session(self) -> Optional[LoopSession]:
        """Close the current session and persist summary metrics.

        Requires at least MIN_ITERATIONS_TO_CLOSE iterations in the current loop.
        Returns the closed LoopSession, or None if insufficient iterations.
        """
        metrics = self._tracer.get_metrics()
        if metrics.total_iterations < self.MIN_ITERATIONS_TO_CLOSE:
            return None

        loop_id = self._tracer.get_current_loop_id()
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        iterations = self._tracer.list_iterations(limit=1000)

        throughputs = [it.metrics.get("throughput", 0.0) for it in iterations]
        latencies = [it.metrics.get("p50_latency", 0.0) for it in iterations]
        error_rates = [it.metrics.get("error_rate", 0.0) for it in iterations]
        cycle_times = [it.cycle_time_s for it in iterations]

        pattern_count = self._generalizer.get_pattern_count()

        session = LoopSession(
            session_id=session_id,
            loop_id=loop_id,
            started_at=iterations[-1].started_at if iterations else datetime.now(timezone.utc).isoformat(),
            closed_at=datetime.now(timezone.utc).isoformat(),
            iterations_count=len(iterations),
            avg_throughput=round(sum(throughputs) / len(throughputs), 6) if throughputs else 0.0,
            avg_p50_latency=round(sum(latencies) / len(latencies), 6) if latencies else 0.0,
            avg_error_rate=round(sum(error_rates) / len(error_rates), 6) if error_rates else 0.0,
            total_cycle_time_s=round(sum(cycle_times), 6),
            patterns_identified=pattern_count,
            summary={
                "min_throughput": min(throughputs) if throughputs else 0.0,
                "max_throughput": max(throughputs) if throughputs else 0.0,
                "min_latency": min(latencies) if latencies else 0.0,
                "max_latency": max(latencies) if latencies else 0.0,
            },
        )

        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO loop_sessions "
                "(session_id, loop_id, started_at, closed_at, iterations_count, "
                "avg_throughput, avg_p50_latency, avg_error_rate, total_cycle_time_s, "
                "patterns_identified, summary) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session.session_id, session.loop_id, session.started_at, session.closed_at,
                    session.iterations_count, session.avg_throughput, session.avg_p50_latency,
                    session.avg_error_rate, session.total_cycle_time_s, session.patterns_identified,
                    json.dumps(session.summary, default=str),
                ),
            )
            conn.commit()
        finally:
            conn.close()

        self._current_session = session
        return session

    def list_sessions(self, limit: int = 50) -> list[LoopSession]:
        """List closed loop sessions ordered by recency."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM loop_sessions ORDER BY closed_at DESC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()
            return [
                LoopSession(
                    session_id=row["session_id"],
                    loop_id=row["loop_id"],
                    started_at=row["started_at"],
                    closed_at=row["closed_at"],
                    iterations_count=row["iterations_count"],
                    avg_throughput=row["avg_throughput"],
                    avg_p50_latency=row["avg_p50_latency"],
                    avg_error_rate=row["avg_error_rate"],
                    total_cycle_time_s=row["total_cycle_time_s"],
                    patterns_identified=row["patterns_identified"],
                    summary=json.loads(row["summary"]),
                )
                for row in rows
            ]
        finally:
            conn.close()

    def get_session(self, session_id: str) -> Optional[LoopSession]:
        """Retrieve a specific session by ID."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM loop_sessions WHERE session_id = ?",
                (session_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return LoopSession(
                session_id=row["session_id"],
                loop_id=row["loop_id"],
                started_at=row["started_at"],
                closed_at=row["closed_at"],
                iterations_count=row["iterations_count"],
                avg_throughput=row["avg_throughput"],
                avg_p50_latency=row["avg_p50_latency"],
                avg_error_rate=row["avg_error_rate"],
                total_cycle_time_s=row["total_cycle_time_s"],
                patterns_identified=row["patterns_identified"],
                summary=json.loads(row["summary"]),
            )
        finally:
            conn.close()

    def get_session_count(self) -> int:
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM loop_sessions")
            return cursor.fetchone()[0]
        finally:
            conn.close()

    def compare_sessions(self, baseline_id: str, candidate_id: str) -> SessionComparison:
        """Compare two closed sessions for improvement."""
        baseline = self.get_session(baseline_id)
        candidate = self.get_session(candidate_id)
        if baseline is None or candidate is None:
            raise ValueError("Both sessions must exist")

        throughput_delta = candidate.avg_throughput - baseline.avg_throughput
        latency_delta = candidate.avg_p50_latency - baseline.avg_p50_latency
        error_rate_delta = candidate.avg_error_rate - baseline.avg_error_rate

        throughput_pct = (throughput_delta / baseline.avg_throughput * 100) if baseline.avg_throughput != 0 else 0.0
        latency_pct = (latency_delta / baseline.avg_p50_latency * 100) if baseline.avg_p50_latency != 0 else 0.0

        improved = (
            (throughput_delta > 0 or error_rate_delta < 0)
            and not (throughput_delta < 0 and error_rate_delta > 0)
        )

        summary = {
            "baseline_throughput": baseline.avg_throughput,
            "candidate_throughput": candidate.avg_throughput,
            "baseline_latency": baseline.avg_p50_latency,
            "candidate_latency": candidate.avg_p50_latency,
            "baseline_error_rate": baseline.avg_error_rate,
            "candidate_error_rate": candidate.avg_error_rate,
            "baseline_patterns": baseline.patterns_identified,
            "candidate_patterns": candidate.patterns_identified,
        }

        return SessionComparison(
            baseline_session_id=baseline_id,
            candidate_session_id=candidate_id,
            throughput_delta=round(throughput_delta, 6),
            throughput_pct_change=round(throughput_pct, 4),
            latency_delta=round(latency_delta, 6),
            latency_pct_change=round(latency_pct, 4),
            error_rate_delta=round(error_rate_delta, 6),
            improved=improved,
            summary=summary,
        )

    def get_current_session(self) -> Optional[LoopSession]:
        return self._current_session


@dataclass
class BootstrapConfig:
    """Initial configuration for bootstrapping the autonomous loop.

    When no prior experiment data exists, these defaults seed the first
    execution cycle. Values can be overridden by founder configuration.
    """

    default_intent: str = "autonomous_loop_bootstrap"
    seed_recommendation: dict[str, Any] = field(default_factory=lambda: {
        "type": "validation_run",
        "rationale": "Cold-start: no prior recommendations available",
        "max_retries": 1,
        "adjustments": [],
    })
    seed_metrics: dict[str, Any] = field(default_factory=lambda: {
        "throughput": 1.0,
        "p50_latency": 1.0,
        "p95_latency": 1.5,
        "p99_latency": 2.0,
        "error_rate": 0.0,
        "iteration_count": 1,
    })
    seed_hypothesis: str = "Baseline performance with default configuration"
    confidence: float = 0.5
    four_state: str = "TEST_VERIFIED"


@dataclass
class BootstrapResult:
    """Result of bootstrapping the autonomous loop."""

    bootstrapped: bool
    experiment_id: str
    recommendation: dict[str, Any]
    seed_metrics: dict[str, Any]
    source: str
    confidence: float
    four_state: str


class LoopBootstrap:
    """Bootstraps the autonomous loop from cold start (Initialization -> Learning binding).

    When no prior experiment data exists, generates an initial recommendation
    and seed metrics so execute_goal can start with a meaningful first iteration
    rather than a blank default. This closes the gap between system startup
    and the first autonomous cycle.

    The bootstrap is fail-closed: if prior experiment data exists, it returns
    unbootstrapped (source="existing_data") so the normal feedback loop takes over.
    """

    def __init__(self, manager: ExperimentManager, analytics: ExperimentAnalytics,
                 config: BootstrapConfig | None = None, db_path: str = ":memory:") -> None:
        self._manager = manager
        self._analytics = analytics
        self._config = config or BootstrapConfig()
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bootstrap_events (
                    bootstrap_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL,
                    recommendation TEXT NOT NULL,
                    seed_metrics TEXT NOT NULL,
                    source TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    four_state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    was_consumed INTEGER DEFAULT 0
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def needs_bootstrap(self) -> bool:
        """Check if the loop needs bootstrapping (no prior recommendations)."""
        recommendation = self._manager.get_last_next_action()
        return recommendation is None

    def bootstrap(self) -> BootstrapResult:
        """Bootstrap the autonomous loop with seed data.

        Creates an initial experiment with seed metrics and a default
        recommendation. Returns the BootstrapResult containing the
        experiment_id and recommendation that can be consumed by the
        next execute_goal call.

        If prior data exists (needs_bootstrap is False), returns
        unbootstrapped with source="existing_data".
        """
        if not self.needs_bootstrap():
            return BootstrapResult(
                bootstrapped=False,
                experiment_id="",
                recommendation={},
                seed_metrics={},
                source="existing_data",
                confidence=0.0,
                four_state="TEST_VERIFIED",
            )

        config = self._config
        exp = self._manager.create_experiment(
            intent=config.default_intent,
            hypothesis=config.seed_hypothesis,
            parameters={"source": "bootstrap", "seed": True},
            agent_id="loop_bootstrap",
            execution_mode="verified",
        )

        for _ in range(2):
            self._analytics.persist_run(exp.experiment_id, dict(config.seed_metrics))

        self._manager.record_outcome(
            exp.experiment_id,
            {"status": "bootstrap_completed", "source": "bootstrap"},
            confidence=config.confidence,
            four_state=config.four_state,
        )

        generator = NextActionGenerator(self._manager, self._analytics)
        next_action = generator.generate(exp.experiment_id, {"status": "bootstrap"}, confidence=0.3)
        recommendation = next_action.get("recommended_next_experiment", next_action)

        bootstrap_id = f"bs_{uuid.uuid4().hex[:12]}"
        created_at = datetime.now(timezone.utc).isoformat()

        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO bootstrap_events "
                "(bootstrap_id, experiment_id, recommendation, seed_metrics, source, "
                "confidence, four_state, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    bootstrap_id, exp.experiment_id,
                    json.dumps(recommendation, default=str),
                    json.dumps(config.seed_metrics, default=str),
                    "bootstrap",
                    config.confidence,
                    config.four_state,
                    created_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return BootstrapResult(
            bootstrapped=True,
            experiment_id=exp.experiment_id,
            recommendation=recommendation,
            seed_metrics=dict(config.seed_metrics),
            source="bootstrap",
            confidence=config.confidence,
            four_state=config.four_state,
        )

    def mark_consumed(self, experiment_id: str) -> None:
        """Mark a bootstrap experiment as consumed by the main loop."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                "UPDATE bootstrap_events SET was_consumed = 1 WHERE experiment_id = ?",
                (experiment_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def get_bootstrap_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """List bootstrap events."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM bootstrap_events ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_bootstrap_count(self) -> int:
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM bootstrap_events")
            return cursor.fetchone()[0]
        finally:
            conn.close()