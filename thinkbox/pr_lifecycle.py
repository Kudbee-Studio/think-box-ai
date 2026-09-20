"""Autonomous PR lifecycle control loop (local SQLite, deterministic).

State machine:
PR_CREATED → IDENTIFY → PROVISION_PERSISTENCE → HEALTH_CHECK → EXECUTE →
OBSERVE → ANALYZE → COMPARE → GENERATE_PROOF → GENERATE_NEXT_ACTION →
APPLY_APPROVAL_BOUNDARY → REPLAY → READY_FOR_CLOSE → CLEANUP → LEARN

Terminal: LEARN (success), FAILED (error), BLOCKED (approval / policy).

Reuses experiment_analytics and pr_db modules. No cloud APIs required in test_mode.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from thinkbox.experiment import ExperimentManager
from thinkbox.experiment_analytics import (
    ApprovalBoundary,
    ExperimentAnalytics,
    ExperimentLifecycle,
    NextActionGenerator,
    ProofDecision,
    ReplayEngine,
)
from thinkbox.pr_db import PRDatabaseConfig, PRDatabaseProvisioner, PRDBState


PR_LIFECYCLE_STATES = [
    "PR_CREATED",
    "IDENTIFY",
    "PROVISION_PERSISTENCE",
    "HEALTH_CHECK",
    "EXECUTE",
    "OBSERVE",
    "ANALYZE",
    "COMPARE",
    "GENERATE_PROOF",
    "GENERATE_NEXT_ACTION",
    "APPLY_APPROVAL_BOUNDARY",
    "REPLAY",
    "READY_FOR_CLOSE",
    "CLEANUP",
    "LEARN",
    "FAILED",
    "BLOCKED",
]

LINEAR_SUCCESS: list[str] = [
    "PR_CREATED",
    "IDENTIFY",
    "PROVISION_PERSISTENCE",
    "HEALTH_CHECK",
    "EXECUTE",
    "OBSERVE",
    "ANALYZE",
    "COMPARE",
    "GENERATE_PROOF",
    "GENERATE_NEXT_ACTION",
    "APPLY_APPROVAL_BOUNDARY",
    "REPLAY",
    "READY_FOR_CLOSE",
    "CLEANUP",
    "LEARN",
]

SUCCESS_TRANSITIONS: dict[str, list[str]] = {}
for i, state in enumerate(LINEAR_SUCCESS[:-1]):
    SUCCESS_TRANSITIONS[state] = [LINEAR_SUCCESS[i + 1]]
SUCCESS_TRANSITIONS["LEARN"] = []
SUCCESS_TRANSITIONS["FAILED"] = []
SUCCESS_TRANSITIONS["BLOCKED"] = []

TERMINAL_STATES = {"LEARN", "FAILED", "BLOCKED"}

# Success-path states that require a recorded approval grant (no snapshot bypass).
_POST_APPROVAL_STATES = frozenset(
    s
    for s in LINEAR_SUCCESS
    if LINEAR_SUCCESS.index(s) > LINEAR_SUCCESS.index("APPLY_APPROVAL_BOUNDARY")
)

GATED_CLOSE_ACTIONS = (
    "merge",
    "deploy_production",
    "infrastructure_change",
    "spend_budget",
    "delete_data",
    "modify_experiment_history",
)


class PRLifecycleState(str, Enum):
    PR_CREATED = "PR_CREATED"
    IDENTIFY = "IDENTIFY"
    PROVISION_PERSISTENCE = "PROVISION_PERSISTENCE"
    HEALTH_CHECK = "HEALTH_CHECK"
    EXECUTE = "EXECUTE"
    OBSERVE = "OBSERVE"
    ANALYZE = "ANALYZE"
    COMPARE = "COMPARE"
    GENERATE_PROOF = "GENERATE_PROOF"
    GENERATE_NEXT_ACTION = "GENERATE_NEXT_ACTION"
    APPLY_APPROVAL_BOUNDARY = "APPLY_APPROVAL_BOUNDARY"
    REPLAY = "REPLAY"
    READY_FOR_CLOSE = "READY_FOR_CLOSE"
    CLEANUP = "CLEANUP"
    LEARN = "LEARN"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


@dataclass
class LifecycleReceipt:
    """Immutable transition record preserving PR identity and evidence."""

    receipt_id: str
    timestamp: str
    run_id: str
    pr_number: int
    branch: str
    from_state: str
    to_state: str
    action: str
    result: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "timestamp": self.timestamp,
            "run_id": self.run_id,
            "pr_number": self.pr_number,
            "branch": self.branch,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "action": self.action,
            "result": self.result,
            "evidence": self.evidence,
        }


@dataclass
class AutonomyScorecard:
    """Raw autonomy metrics only — no composite score."""

    transitions_completed: int = 0
    transitions_failed: int = 0
    receipts_count: int = 0
    autonomous_actions_taken: int = 0
    approval_gates_encountered: int = 0
    approval_denied_count: int = 0
    replay_performed: bool = False
    cleanup_performed: bool = False
    cleanup_idempotent_calls: int = 0
    terminal_state: str = ""
    stages_visited: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "transitions_completed": self.transitions_completed,
            "transitions_failed": self.transitions_failed,
            "receipts_count": self.receipts_count,
            "autonomous_actions_taken": self.autonomous_actions_taken,
            "approval_gates_encountered": self.approval_gates_encountered,
            "approval_denied_count": self.approval_denied_count,
            "replay_performed": self.replay_performed,
            "cleanup_performed": self.cleanup_performed,
            "cleanup_idempotent_calls": self.cleanup_idempotent_calls,
            "terminal_state": self.terminal_state,
            "stages_visited": list(self.stages_visited),
        }


@dataclass
class PRLifecycleConfig:
    pr_number: int
    branch: str = ""
    test_mode: bool = True
    close_action: str = "merge"
    approvals: dict[str, bool] = field(default_factory=dict)
    inject_failure_at: Optional[str] = None
    skip_cleanup: bool = False
    deterministic_metrics: Optional[list[dict[str, Any]]] = None
    provisioner_state_path: Optional[str] = None


@dataclass
class PRLifecycleResult:
    terminal_state: str
    run_id: str
    pr_number: int
    branch: str
    receipts: list[dict[str, Any]]
    scorecard: dict[str, Any]
    context: dict[str, Any]
    error: Optional[str] = None


class PRLifecycle:
    """Validates PR lifecycle state transitions."""

    VALID_TRANSITIONS: dict[str, list[str]] = SUCCESS_TRANSITIONS

    @classmethod
    def can_transition(cls, from_state: str, to_state: str) -> bool:
        if to_state in ("FAILED", "BLOCKED"):
            return from_state not in TERMINAL_STATES
        return to_state in cls.VALID_TRANSITIONS.get(from_state, [])

    @classmethod
    def validate_transition(cls, from_state: str, to_state: str) -> None:
        if from_state not in PR_LIFECYCLE_STATES:
            raise ValueError(f"Invalid from_state: {from_state}")
        if to_state not in PR_LIFECYCLE_STATES:
            raise ValueError(f"Invalid to_state: {to_state}")
        if not cls.can_transition(from_state, to_state):
            raise ValueError(
                f"Invalid transition: {from_state} → {to_state}. "
                f"Valid: {cls.VALID_TRANSITIONS.get(from_state, [])}"
            )

    @classmethod
    def is_terminal(cls, state: str) -> bool:
        return state in TERMINAL_STATES


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_metric_runs() -> list[dict[str, Any]]:
    return [
        {
            "throughput": 10.0,
            "p50_latency": 0.3,
            "p95_latency": 0.5,
            "p99_latency": 0.8,
            "error_rate": 0.01,
            "iteration_count": 1,
        },
        {
            "throughput": 12.0,
            "p50_latency": 0.28,
            "p95_latency": 0.48,
            "p99_latency": 0.75,
            "error_rate": 0.008,
            "iteration_count": 2,
        },
    ]


class PRLifecycleOrchestrator:
    """Smallest autonomous orchestrator: one transition per step, explicit failures."""

    def __init__(self, config: PRLifecycleConfig) -> None:
        self._config = config
        self._state = PRLifecycleState.PR_CREATED.value
        self._run_id = f"pr_run_{uuid.uuid4().hex[:12]}"
        self._receipts: list[LifecycleReceipt] = []
        self._scorecard = AutonomyScorecard()
        self._context: dict[str, Any] = {
            "run_id": self._run_id,
            "pr_number": config.pr_number,
            "branch": config.branch,
        }
        self._provisioner: Optional[PRDatabaseProvisioner] = None
        self._manager: Optional[ExperimentManager] = None
        self._analytics: Optional[ExperimentAnalytics] = None
        self._boundary = ApprovalBoundary(ExperimentManager(db_path=":memory:"))

    @property
    def current_state(self) -> str:
        return self._state

    @property
    def receipts(self) -> list[LifecycleReceipt]:
        return list(self._receipts)

    @property
    def scorecard(self) -> AutonomyScorecard:
        return self._scorecard

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def context(self) -> dict[str, Any]:
        return dict(self._context)

    def snapshot(self) -> dict[str, Any]:
        """Serializable checkpoint for crash-resume (no open handles)."""
        return {
            "run_id": self._run_id,
            "state": self._state,
            "context": dict(self._context),
            "receipts": [r.to_dict() for r in self._receipts],
            "scorecard": self._scorecard.to_dict(),
        }

    @classmethod
    def validate_snapshot(cls, data: dict[str, Any]) -> None:
        """Fail-closed validation before restore (malformed / approval bypass)."""
        if not isinstance(data, dict):
            raise ValueError("snapshot must be a dict")
        if "run_id" not in data:
            raise ValueError("snapshot missing run_id")
        state = data.get("state")
        if state not in PR_LIFECYCLE_STATES:
            raise ValueError(f"snapshot invalid state: {state}")
        if PRLifecycle.is_terminal(state):
            raise ValueError(f"cannot restore terminal snapshot state: {state}")
        receipts_raw = data.get("receipts") or []
        if receipts_raw:
            last_to = receipts_raw[-1].get("to_state")
            if last_to and last_to != state and last_to not in TERMINAL_STATES:
                raise ValueError(
                    f"snapshot state/receipt mismatch: state={state} last_receipt_to={last_to}"
                )
        if state in _POST_APPROVAL_STATES:
            granted = any(
                r.get("action") == "approval_granted" and r.get("result") == "success"
                for r in receipts_raw
            )
            if not granted:
                raise ValueError(
                    f"snapshot bypass: state {state} requires prior approval_granted receipt"
                )

    def restore_snapshot(self, data: dict[str, Any]) -> None:
        """Restore orchestrator from snapshot; rehydrates DB handles on next step."""
        self.validate_snapshot(data)
        self._run_id = data["run_id"]
        self._state = data["state"]
        self._context = dict(data["context"])
        self._receipts = []
        for raw in data.get("receipts", []):
            self._receipts.append(
                LifecycleReceipt(
                    receipt_id=raw["receipt_id"],
                    timestamp=raw["timestamp"],
                    run_id=raw["run_id"],
                    pr_number=raw["pr_number"],
                    branch=raw["branch"],
                    from_state=raw["from_state"],
                    to_state=raw["to_state"],
                    action=raw["action"],
                    result=raw["result"],
                    evidence=dict(raw.get("evidence", {})),
                )
            )
        sc = data.get("scorecard", {})
        self._scorecard = AutonomyScorecard(
            transitions_completed=sc.get("transitions_completed", 0),
            transitions_failed=sc.get("transitions_failed", 0),
            receipts_count=sc.get("receipts_count", 0),
            autonomous_actions_taken=sc.get("autonomous_actions_taken", 0),
            approval_gates_encountered=sc.get("approval_gates_encountered", 0),
            approval_denied_count=sc.get("approval_denied_count", 0),
            replay_performed=sc.get("replay_performed", False),
            cleanup_performed=sc.get("cleanup_performed", False),
            cleanup_idempotent_calls=sc.get("cleanup_idempotent_calls", 0),
            terminal_state=sc.get("terminal_state", ""),
            stages_visited=list(sc.get("stages_visited", [])),
        )
        self._provisioner = None
        self._manager = None
        self._analytics = None

    def _rehydrate_runtime(self) -> None:
        """Rebuild provisioner/manager after process restart from persisted PR DB state."""
        if self._manager is not None:
            return
        db_id = self._context.get("db_id")
        state_path = self._context.get("provisioner_state_path") or self._config.provisioner_state_path
        if not db_id or not state_path:
            return
        db_config = PRDatabaseConfig(
            pr_number=self._config.pr_number,
            branch=self._config.branch,
            test_mode=self._config.test_mode,
            state_file=state_path,
        )
        self._provisioner = PRDatabaseProvisioner(db_config)
        self._manager = self._provisioner.get_manager(db_id)
        self._analytics = ExperimentAnalytics(self._manager)
        self._boundary = ApprovalBoundary(self._manager)

    def _emit_receipt(
        self,
        from_state: str,
        to_state: str,
        action: str,
        result: str,
        evidence: Optional[dict[str, Any]] = None,
    ) -> LifecycleReceipt:
        receipt = LifecycleReceipt(
            receipt_id=f"rcpt_{uuid.uuid4().hex[:12]}",
            timestamp=_utc_now_iso(),
            run_id=self._run_id,
            pr_number=self._config.pr_number,
            branch=self._config.branch,
            from_state=from_state,
            to_state=to_state,
            action=action,
            result=result,
            evidence=evidence or {},
        )
        self._receipts.append(receipt)
        self._scorecard.receipts_count += 1
        if to_state not in self._scorecard.stages_visited:
            self._scorecard.stages_visited.append(to_state)
        return receipt

    def _fail(self, from_state: str, action: str, reason: str, evidence: dict[str, Any]) -> None:
        self._scorecard.transitions_failed += 1
        self._state = PRLifecycleState.FAILED.value
        self._scorecard.terminal_state = self._state
        self._emit_receipt(from_state, self._state, action, "failure", {**evidence, "error": reason})

    def _block(self, from_state: str, action: str, reason: str, evidence: dict[str, Any]) -> None:
        self._scorecard.approval_denied_count += 1
        self._state = PRLifecycleState.BLOCKED.value
        self._scorecard.terminal_state = self._state
        self._emit_receipt(from_state, self._state, action, "blocked", {**evidence, "error": reason})

    def _advance(self, to_state: str, action: str, evidence: dict[str, Any]) -> None:
        from_state = self._state
        PRLifecycle.validate_transition(from_state, to_state)
        self._state = to_state
        self._scorecard.transitions_completed += 1
        self._emit_receipt(from_state, to_state, action, "success", evidence)

    def _check_injected_failure(self, stage: str) -> bool:
        return self._config.inject_failure_at == stage

    def step(self) -> LifecycleReceipt:
        """Execute exactly one lifecycle transition. Fail-closed on invalid state."""
        if PRLifecycle.is_terminal(self._state):
            raise RuntimeError(f"Orchestrator already terminal: {self._state}")

        stage = self._state
        try:
            self._rehydrate_runtime()
        except Exception as exc:
            self._fail(stage, "rehydrate_runtime", str(exc), {})
            return self._receipts[-1]
        if self._check_injected_failure(stage):
            self._fail(stage, f"{stage}_action", f"injected_failure_at_{stage}", {})
            return self._receipts[-1]

        if stage == PRLifecycleState.PR_CREATED.value:
            self._advance(PRLifecycleState.IDENTIFY.value, "identify_pr", {"pr_number": self._config.pr_number})
        elif stage == PRLifecycleState.IDENTIFY.value:
            self._context["identified_at"] = _utc_now_iso()
            self._advance(
                PRLifecycleState.PROVISION_PERSISTENCE.value,
                "identify_complete",
                {"branch": self._config.branch, "pr_number": self._config.pr_number},
            )
        elif stage == PRLifecycleState.PROVISION_PERSISTENCE.value:
            try:
                if self._context.get("db_id") and self._context.get("provisioner_state_path"):
                    self._rehydrate_runtime()
                    record_db = self._context["db_id"]
                    self._advance(
                        PRLifecycleState.HEALTH_CHECK.value,
                        "provision_persistence_idempotent",
                        {"db_id": record_db, "idempotent": True},
                    )
                    return self._receipts[-1]
                state_path = (
                    self._config.provisioner_state_path
                    or self._context.get("provisioner_state_path")
                    or os.path.join(
                        tempfile.gettempdir(),
                        f"prdb_state_{self._config.pr_number}_{self._run_id}.json",
                    )
                )
                db_config = PRDatabaseConfig(
                    pr_number=self._config.pr_number,
                    branch=self._config.branch,
                    test_mode=self._config.test_mode,
                    state_file=state_path,
                )
                self._provisioner = PRDatabaseProvisioner(db_config)
                record = self._provisioner.provision()
                self._provisioner.activate(record.db_id)
                self._manager = self._provisioner.get_manager(record.db_id)
                self._analytics = ExperimentAnalytics(self._manager)
                self._boundary = ApprovalBoundary(self._manager)
                self._context["db_id"] = record.db_id
                self._context["provisioner_state_path"] = self._provisioner.state_path
                self._advance(
                    PRLifecycleState.HEALTH_CHECK.value,
                    "provision_persistence",
                    {"db_id": record.db_id, "db_type": record.db_type},
                )
            except Exception as exc:
                self._fail(stage, "provision_persistence", str(exc), {})
        elif stage == PRLifecycleState.HEALTH_CHECK.value:
            db_id = self._context.get("db_id", "")
            health = self._provisioner.health_check(db_id) if self._provisioner else {"healthy": False}
            if not health.get("healthy"):
                self._fail(stage, "health_check", "health_check_failed", health)
            else:
                self._advance(PRLifecycleState.EXECUTE.value, "health_check", health)
        elif stage == PRLifecycleState.EXECUTE.value:
            try:
                if self._context.get("experiment_id"):
                    exp_id = self._context["experiment_id"]
                    self._advance(
                        PRLifecycleState.OBSERVE.value,
                        "execute_experiment_idempotent",
                        {"experiment_id": exp_id, "idempotent": True},
                    )
                    return self._receipts[-1]
                exp_id = self._execute_local_experiment()
                self._context["experiment_id"] = exp_id
                self._scorecard.autonomous_actions_taken += 1
                self._advance(PRLifecycleState.OBSERVE.value, "execute_experiment", {"experiment_id": exp_id})
            except Exception as exc:
                self._fail(stage, "execute_experiment", str(exc), {})
        elif stage == PRLifecycleState.OBSERVE.value:
            exp_id = self._context["experiment_id"]
            arts = self._analytics._query_artifacts(exp_id) if self._analytics else []
            self._context["artifact_count"] = len(arts)
            self._advance(PRLifecycleState.ANALYZE.value, "observe_artifacts", {"artifact_count": len(arts)})
        elif stage == PRLifecycleState.ANALYZE.value:
            try:
                exp_id = self._context["experiment_id"]
                metrics = self._analytics.aggregate_metrics(exp_id)
                self._context["metrics_summary"] = metrics.get("summary", {})
                self._advance(PRLifecycleState.COMPARE.value, "analyze_metrics", {"n_runs": metrics["n_runs"]})
            except Exception as exc:
                self._fail(stage, "analyze_metrics", str(exc), {})
        elif stage == PRLifecycleState.COMPARE.value:
            try:
                exp_id = self._context["experiment_id"]
                comparison = self._analytics.compare_runs(exp_id)
                self._context["comparison"] = comparison
                self._advance(
                    PRLifecycleState.GENERATE_PROOF.value,
                    "compare_runs",
                    {"n_comparisons": comparison["n_comparisons"]},
                )
            except Exception as exc:
                self._fail(stage, "compare_runs", str(exc), {})
        elif stage == PRLifecycleState.GENERATE_PROOF.value:
            try:
                if self._context.get("proof_sha256"):
                    proof_hash = self._context["proof_sha256"]
                    self._advance(
                        PRLifecycleState.GENERATE_NEXT_ACTION.value,
                        "generate_proof_idempotent",
                        {"proof_sha256": proof_hash, "idempotent": True},
                    )
                    return self._receipts[-1]
                proof_hash = self._generate_proof()
                self._context["proof_sha256"] = proof_hash
                self._advance(PRLifecycleState.GENERATE_NEXT_ACTION.value, "generate_proof", {"proof_sha256": proof_hash})
            except Exception as exc:
                self._fail(stage, "generate_proof", str(exc), {})
        elif stage == PRLifecycleState.GENERATE_NEXT_ACTION.value:
            try:
                if self._context.get("next_action_id"):
                    self._advance(
                        PRLifecycleState.APPLY_APPROVAL_BOUNDARY.value,
                        "generate_next_action_idempotent",
                        {"next_action_id": self._context["next_action_id"], "idempotent": True},
                    )
                    return self._receipts[-1]
                exp_id = self._context["experiment_id"]
                generator = NextActionGenerator(self._manager, self._analytics)
                outcome = {"status": "completed", "source": "pr_lifecycle_local"}
                next_action = generator.generate(exp_id, outcome, confidence=0.9)
                self._context["next_action_id"] = next_action["next_action_id"]
                self._scorecard.autonomous_actions_taken += 1
                self._advance(
                    PRLifecycleState.APPLY_APPROVAL_BOUNDARY.value,
                    "generate_next_action",
                    {"next_action_id": next_action["next_action_id"]},
                )
            except Exception as exc:
                self._fail(stage, "generate_next_action", str(exc), {})
        elif stage == PRLifecycleState.APPLY_APPROVAL_BOUNDARY.value:
            self._apply_approval_boundary()
        elif stage == PRLifecycleState.REPLAY.value:
            try:
                if self._context.get("replay_runs") is not None:
                    self._advance(
                        PRLifecycleState.READY_FOR_CLOSE.value,
                        "replay_from_evidence_idempotent",
                        {"replay_runs": self._context["replay_runs"], "idempotent": True},
                    )
                    return self._receipts[-1]
                exp_id = self._context["experiment_id"]
                replayer = ReplayEngine(self._manager, self._analytics)
                replay = replayer.replay(exp_id)
                self._context["replay_runs"] = replay["metrics"]["n_runs"]
                self._scorecard.replay_performed = True
                self._scorecard.autonomous_actions_taken += 1
                self._advance(
                    PRLifecycleState.READY_FOR_CLOSE.value,
                    "replay_from_evidence",
                    {"replay_runs": replay["metrics"]["n_runs"]},
                )
            except Exception as exc:
                self._fail(stage, "replay_from_evidence", str(exc), {})
        elif stage == PRLifecycleState.READY_FOR_CLOSE.value:
            required = ("experiment_id", "proof_sha256", "next_action_id", "replay_runs")
            missing = [k for k in required if k not in self._context]
            if missing:
                self._fail(stage, "ready_for_close", f"missing_evidence:{missing}", {})
            else:
                self._record_experiment_learned()
                self._advance(PRLifecycleState.CLEANUP.value, "ready_for_close", {"evidence_complete": True})
        elif stage == PRLifecycleState.CLEANUP.value:
            if self._config.skip_cleanup:
                self._advance(PRLifecycleState.LEARN.value, "cleanup_skipped", {"skip_cleanup": True})
            else:
                try:
                    db_id = self._context["db_id"]
                    self._provisioner.cleanup(db_id)
                    self._scorecard.cleanup_performed = True
                    self._provisioner.cleanup(db_id)
                    self._scorecard.cleanup_idempotent_calls += 1
                    self._advance(PRLifecycleState.LEARN.value, "cleanup", {"db_id": db_id})
                except Exception as exc:
                    self._fail(stage, "cleanup", str(exc), {})
        elif stage == PRLifecycleState.LEARN.value:
            raise RuntimeError("LEARN is terminal; call run() to finalize")
        else:
            self._fail(stage, "unknown_state", f"unknown_state:{stage}", {})

        return self._receipts[-1]

    def run(
        self,
        execute_fn: Optional[Callable[[ExperimentManager, ExperimentAnalytics], str]] = None,
    ) -> PRLifecycleResult:
        """Run until terminal state. Optional execute_fn overrides local EXECUTE."""
        if getattr(self, "_resilience_wrapped", False):
            raise RuntimeError(
                "orchestrator.run() disabled under ResilientPRLifecycleRunner; "
                "use run_to_completion() or step_resilient()"
            )
        self._execute_override = execute_fn
        while not PRLifecycle.is_terminal(self._state):
            self.step()
        if self._state == PRLifecycleState.LEARN.value:
            self._finalize_learn()
        self._scorecard.terminal_state = self._state
        err = None
        if self._state == PRLifecycleState.FAILED.value:
            err = self._receipts[-1].evidence.get("error", "failed")
        if self._state == PRLifecycleState.BLOCKED.value:
            err = self._receipts[-1].evidence.get("error", "blocked")
        return PRLifecycleResult(
            terminal_state=self._state,
            run_id=self._run_id,
            pr_number=self._config.pr_number,
            branch=self._config.branch,
            receipts=[r.to_dict() for r in self._receipts],
            scorecard=self._scorecard.to_dict(),
            context=dict(self._context),
            error=err,
        )

    def _find_lifecycle_experiment_id(self) -> Optional[str]:
        assert self._manager is not None
        intent = f"pr-{self._config.pr_number}-lifecycle"
        rows = [
            row
            for row in self._manager.db.get_all_experiments(limit=100)
            if row.get("intent") == intent
        ]
        if not rows:
            return None
        rows.sort(key=lambda row: row.get("timestamp", ""))
        return rows[0]["experiment_id"]

    def _execute_local_experiment(self) -> str:
        if getattr(self, "_execute_override", None):
            return self._execute_override(self._manager, self._analytics)

        assert self._manager is not None and self._analytics is not None
        exp_id = self._find_lifecycle_experiment_id()
        if not exp_id:
            exp = self._manager.create_experiment(
                intent=f"pr-{self._config.pr_number}-lifecycle",
                hypothesis="Local deterministic PR lifecycle experiment",
                agent_id="pr_lifecycle_orchestrator",
            )
            exp_id = exp.experiment_id
        runs = self._config.deterministic_metrics or _default_metric_runs()
        if not self._analytics._query_artifacts(exp_id):
            for run in runs:
                self._analytics.persist_run(exp_id, run)
            self._manager.record_outcome(
                exp_id,
                {"status": "completed", "runs": len(runs)},
                confidence=0.9,
            )
            lifecycle = ExperimentLifecycle(self._manager, exp_id)
            for target in ("RUNNING", "OBSERVED", "VERIFIED"):
                lifecycle.transition(target, evidence={"source": "pr_lifecycle_execute"})
        return exp_id

    def _generate_proof(self) -> str:
        assert self._manager is not None
        exp_id = self._context["experiment_id"]
        proof_payload = {
            "experiment_id": exp_id,
            "pr_number": self._config.pr_number,
            "branch": self._config.branch,
            "metrics_summary": self._context.get("metrics_summary", {}),
            "comparison_n": self._context.get("comparison", {}).get("n_comparisons", 0),
            "run_id": self._run_id,
        }
        hash_payload = dict(proof_payload)
        if self._config.test_mode:
            hash_payload.pop("run_id", None)
            hash_payload["experiment_id"] = f"deterministic-pr-{self._config.pr_number}"
        raw = json.dumps(hash_payload, sort_keys=True, default=str).encode()
        proof_hash = hashlib.sha256(raw).hexdigest()
        proof_payload["proof_sha256"] = proof_hash
        self._manager.add_proof(exp_id, proof_payload)
        ProofDecision(self._manager).record(
            experiment_id=exp_id,
            decision="pr_lifecycle_proof",
            proof_sha256=proof_hash,
            metrics=self._context.get("metrics_summary", {}),
            confidence=0.9,
        )
        return proof_hash

    def _apply_approval_boundary(self) -> None:
        stage = PRLifecycleState.APPLY_APPROVAL_BOUNDARY.value
        close_action = self._config.close_action
        if close_action not in GATED_CLOSE_ACTIONS:
            self._fail(stage, "approval_boundary", f"unknown_gated_action:{close_action}", {})

        if not self._boundary.requires_approval(close_action):
            self._fail(stage, "approval_boundary", f"action_not_gated:{close_action}", {})

        self._scorecard.approval_gates_encountered += 1
        approved = self._config.approvals.get(close_action)
        if approved is not True:
            self._block(
                stage,
                "approval_boundary",
                f"approval_required_not_granted:{close_action}",
                {"action": close_action, "approved": approved},
            )
            return

        exp_id = self._context["experiment_id"]
        self._boundary.record_decision(exp_id, close_action, approved=True, approver="test_approver")
        self._advance(PRLifecycleState.REPLAY.value, "approval_granted", {"action": close_action})

    def _record_experiment_learned(self) -> None:
        """Persist experiment lifecycle before PR DB cleanup removes SQLite files."""
        exp_id = self._context.get("experiment_id")
        if not self._manager or not exp_id:
            return
        lifecycle = ExperimentLifecycle(self._manager, exp_id)
        for target in ("COMPARED", "LEARNED"):
            try:
                lifecycle.transition(target, evidence={"source": "pr_lifecycle_learn"})
            except ValueError:
                pass

    def _finalize_learn(self) -> None:
        receipt = LifecycleReceipt(
            receipt_id=f"rcpt_{uuid.uuid4().hex[:12]}",
            timestamp=_utc_now_iso(),
            run_id=self._run_id,
            pr_number=self._config.pr_number,
            branch=self._config.branch,
            from_state=PRLifecycleState.LEARN.value,
            to_state=PRLifecycleState.LEARN.value,
            action="learn_complete",
            result="success",
            evidence={"run_id": self._run_id},
        )
        self._receipts.append(receipt)
        self._scorecard.receipts_count += 1
