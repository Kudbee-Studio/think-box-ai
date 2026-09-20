"""Stress-resilience layer for PR lifecycle: retries, crash-resume, concurrency, guards.

Local SQLite / test_mode only. No cloud dependencies.
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from thinkbox.pr_lifecycle import (
    LINEAR_SUCCESS,
    PRLifecycle,
    PRLifecycleConfig,
    PRLifecycleOrchestrator,
    PRLifecycleResult,
    PRLifecycleState,
    TERMINAL_STATES,
)

# Conceptual loop boundaries mapped to orchestrator states (INTENT/PLAN → IDENTIFY).
BOUNDARY_STAGES: tuple[str, ...] = (
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
    "CLEANUP",
)


@dataclass(frozen=True)
class RecoveryPolicy:
    """Per-boundary recovery contract."""

    boundary: str
    retryable: bool
    max_retries: int
    exhausted_terminal: str  # FAILED or BLOCKED
    human_escalation: bool
    evidence_required: bool = True


RECOVERY_MATRIX: dict[str, RecoveryPolicy] = {
    stage: RecoveryPolicy(
        boundary=stage,
        retryable=stage not in ("APPLY_APPROVAL_BOUNDARY",),
        max_retries=2 if stage not in ("APPLY_APPROVAL_BOUNDARY",) else 0,
        exhausted_terminal="BLOCKED" if stage == "APPLY_APPROVAL_BOUNDARY" else "FAILED",
        human_escalation=stage in ("APPLY_APPROVAL_BOUNDARY", "CLEANUP"),
    )
    for stage in BOUNDARY_STAGES
}


@dataclass
class ResilienceConfig:
    """Safety limits and transient failure injection for stress runs."""

    base: PRLifecycleConfig
    max_total_steps: int = 200
    max_autonomous_actions: int = 50
    max_experiments: int = 5
    max_retry_events: int = 100
    transient_failures: dict[str, int] = field(default_factory=dict)
    checkpoint_dir: Optional[str] = None
    initiator: str = "resilient_runner"


@dataclass
class AuditEnvelope:
    """Mandatory audit fields for every resilient action."""

    initiator: str
    state: str
    why: str
    evidence: dict[str, Any]
    delta: dict[str, Any]
    next_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "initiator": self.initiator,
            "state": self.state,
            "why": self.why,
            "evidence": self.evidence,
            "delta": self.delta,
            "next": self.next_action,
        }


@dataclass
class ResilienceScorecard:
    """Raw counts only — extends base autonomy metrics."""

    retries_attempted: int = 0
    retries_succeeded: int = 0
    retries_exhausted: int = 0
    checkpoints_written: int = 0
    crash_resumes: int = 0
    safety_blocks: int = 0
    boundary_failures_injected: int = 0
    parallel_runs_started: int = 0
    parallel_runs_completed: int = 0
    audit_records: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "retries_attempted": self.retries_attempted,
            "retries_succeeded": self.retries_succeeded,
            "retries_exhausted": self.retries_exhausted,
            "checkpoints_written": self.checkpoints_written,
            "crash_resumes": self.crash_resumes,
            "safety_blocks": self.safety_blocks,
            "boundary_failures_injected": self.boundary_failures_injected,
            "parallel_runs_started": self.parallel_runs_started,
            "parallel_runs_completed": self.parallel_runs_completed,
            "audit_records": self.audit_records,
        }


@dataclass
class FourStateVerdict:
    code_complete: bool
    test_verified: bool
    live_verified: bool
    production_ready: bool
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "CODE_COMPLETE": self.code_complete,
            "TEST_VERIFIED": self.test_verified,
            "LIVE_VERIFIED": self.live_verified,
            "PRODUCTION_READY": self.production_ready,
            "notes": list(self.notes),
        }


class PRLifecycleCheckpointStore:
    """SQLite-backed orchestrator checkpoints (one row per run_id)."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lifecycle_checkpoints (
                run_id TEXT PRIMARY KEY,
                pr_number INTEGER NOT NULL,
                branch TEXT,
                state TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()

    def save(self, run_id: str, pr_number: int, branch: str, snapshot: dict[str, Any]) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            """
            INSERT INTO lifecycle_checkpoints (run_id, pr_number, branch, state, snapshot_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                state=excluded.state,
                snapshot_json=excluded.snapshot_json,
                updated_at=excluded.updated_at
            """,
            (
                run_id,
                pr_number,
                branch,
                snapshot.get("state", ""),
                json.dumps(snapshot, sort_keys=True, default=str),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        conn.close()

    def load(self, run_id: str) -> Optional[dict[str, Any]]:
        conn = sqlite3.connect(self._db_path)
        row = conn.execute(
            "SELECT snapshot_json FROM lifecycle_checkpoints WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        conn.close()
        if not row:
            return None
        return json.loads(row[0])

    def delete(self, run_id: str) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.execute("DELETE FROM lifecycle_checkpoints WHERE run_id = ?", (run_id,))
        conn.commit()
        conn.close()


class ResilientPRLifecycleRunner:
    """Wraps PRLifecycleOrchestrator with retries, checkpoints, audit, and guards."""

    def __init__(self, config: ResilienceConfig) -> None:
        self._config = config
        self._orch = PRLifecycleOrchestrator(config.base)
        self._orch._resilience_wrapped = True  # noqa: SLF001 — fail-closed duplicate orchestration
        self._resilience_score = ResilienceScorecard()
        self._audit_log: list[dict[str, Any]] = []
        self._retry_counts: dict[str, int] = {b: 0 for b in BOUNDARY_STAGES}
        self._transient_remaining: dict[str, int] = dict(config.transient_failures)
        self._steps_taken = 0
        ck_dir = config.checkpoint_dir or tempfile.mkdtemp(prefix="pr_lifecycle_ck_")
        self._store = PRLifecycleCheckpointStore(os.path.join(ck_dir, "checkpoints.db"))
        self._prev_context: dict[str, Any] = {}

    @property
    def orchestrator(self) -> PRLifecycleOrchestrator:
        return self._orch

    @property
    def resilience_scorecard(self) -> ResilienceScorecard:
        return self._resilience_score

    @property
    def audit_log(self) -> list[dict[str, Any]]:
        return list(self._audit_log)

    @classmethod
    def resume_from_checkpoint(
        cls,
        config: ResilienceConfig,
        run_id: str,
    ) -> "ResilientPRLifecycleRunner":
        ck_dir = config.checkpoint_dir or tempfile.mkdtemp(prefix="pr_lifecycle_ck_")
        store = PRLifecycleCheckpointStore(os.path.join(ck_dir, "checkpoints.db"))
        snapshot = store.load(run_id)
        if snapshot is None:
            raise ValueError(f"No checkpoint for run_id={run_id}")
        runner = cls(config)
        runner._orch.restore_snapshot(snapshot)
        runner._resilience_score.crash_resumes += 1
        runner._prev_context = dict(runner._orch.context)
        return runner

    def _expected_next(self, state: str) -> str:
        if state in LINEAR_SUCCESS:
            idx = LINEAR_SUCCESS.index(state)
            if idx + 1 < len(LINEAR_SUCCESS):
                return LINEAR_SUCCESS[idx + 1]
        return ""

    def _record_audit(
        self,
        why: str,
        evidence: dict[str, Any],
        delta: dict[str, Any],
        next_action: str,
    ) -> None:
        env = AuditEnvelope(
            initiator=self._config.initiator,
            state=self._orch.current_state,
            why=why,
            evidence=evidence,
            delta=delta,
            next_action=next_action,
        )
        self._audit_log.append(env.to_dict())
        self._resilience_score.audit_records += 1

    def _checkpoint(self) -> None:
        snap = self._orch.snapshot()
        self._store.save(
            self._orch.run_id,
            self._config.base.pr_number,
            self._config.base.branch,
            snap,
        )
        self._resilience_score.checkpoints_written += 1

    def _policy_for(self, boundary: str) -> RecoveryPolicy:
        return RECOVERY_MATRIX.get(
            boundary,
            RecoveryPolicy(boundary, True, 2, "FAILED", False),
        )

    def _safety_block(self, reason: str) -> PRLifecycleResult:
        self._resilience_score.safety_blocks += 1
        self._orch._state = PRLifecycleState.BLOCKED.value
        self._orch._scorecard.terminal_state = PRLifecycleState.BLOCKED.value
        self._orch._emit_receipt(
            self._orch.current_state,
            PRLifecycleState.BLOCKED.value,
            "safety_guard",
            "blocked",
            {"error": reason, "human_gate": True},
        )
        self._record_audit(reason, {"guard": reason}, {}, "human_approval_required")
        return self._finalize_result(error=reason)

    def _check_safety_guards(self) -> Optional[PRLifecycleResult]:
        if self._steps_taken >= self._config.max_total_steps:
            return self._safety_block("max_total_steps_exceeded")
        if self._orch.scorecard.autonomous_actions_taken >= self._config.max_autonomous_actions:
            return self._safety_block("max_autonomous_actions_exceeded")
        exp_count = 1 if self._orch.context.get("experiment_id") else 0
        if exp_count > self._config.max_experiments:
            return self._safety_block("max_experiments_exceeded")
        total_retries = sum(self._retry_counts.values())
        if total_retries > self._config.max_retry_events:
            return self._safety_block("max_retry_events_exceeded")
        return None

    def _maybe_transient_failure(self, boundary: str) -> bool:
        remaining = self._transient_remaining.get(boundary, 0)
        if remaining <= 0:
            return False
        self._transient_remaining[boundary] = remaining - 1
        self._resilience_score.boundary_failures_injected += 1
        return True

    def step_resilient(self) -> dict[str, Any]:
        """One resilient step with retry matrix and audit."""
        if PRLifecycle.is_terminal(self._orch.current_state):
            raise RuntimeError(f"Already terminal: {self._orch.current_state}")

        blocked = self._check_safety_guards()
        if blocked is not None:
            return {"terminal": True, "result": blocked}

        boundary = self._orch.current_state
        if boundary == PRLifecycleState.PR_CREATED.value:
            boundary = "IDENTIFY"

        policy = self._policy_for(boundary) if boundary in BOUNDARY_STAGES else None
        ctx_before = dict(self._orch.context)

        while True:
            if self._maybe_transient_failure(boundary):
                self._resilience_score.retries_attempted += 1
                self._retry_counts[boundary] = self._retry_counts.get(boundary, 0) + 1
                policy = policy or self._policy_for(boundary)
                if not policy.retryable or self._retry_counts[boundary] > policy.max_retries:
                    self._resilience_score.retries_exhausted += 1
                    reason = f"transient_failure_exhausted:{boundary}"
                    evidence = {
                        "retry_count": self._retry_counts[boundary],
                        "policy": policy.boundary,
                    }
                    if policy.exhausted_terminal == "BLOCKED":
                        self._orch._block(
                            boundary,
                            f"{boundary}_transient",
                            reason,
                            evidence,
                        )
                    else:
                        self._orch._fail(
                            boundary,
                            f"{boundary}_transient",
                            reason,
                            evidence,
                        )
                    self._record_audit(
                        "transient_failure_exhausted",
                        {"boundary": boundary},
                        {},
                        policy.exhausted_terminal,
                    )
                    return {
                        "receipt": self._orch.receipts[-1].to_dict(),
                        "state": self._orch.current_state,
                        "terminal": True,
                    }
                self._record_audit(
                    "transient_failure_retry",
                    {"boundary": boundary, "attempt": self._retry_counts[boundary]},
                    {},
                    "retry_same_boundary",
                )
                continue

            receipt = self._orch.step()
            self._steps_taken += 1
            delta = {
                k: self._orch.context.get(k)
                for k in set(self._orch.context) - set(ctx_before)
            }
            self._record_audit(
                receipt.action,
                receipt.evidence,
                delta,
                self._expected_next(receipt.to_state),
            )
            if receipt.result == "success":
                self._resilience_score.retries_succeeded += int(
                    self._retry_counts.get(boundary, 0) > 0
                )
            self._checkpoint()
            self._prev_context = dict(self._orch.context)
            break

        return {
            "receipt": self._orch.receipts[-1].to_dict(),
            "state": self._orch.current_state,
            "terminal": PRLifecycle.is_terminal(self._orch.current_state),
        }

    def run_to_completion(
        self,
        crash_after_steps: Optional[int] = None,
    ) -> PRLifecycleResult:
        """Run loop; optionally simulate crash after N resilient steps."""
        steps = 0
        while not PRLifecycle.is_terminal(self._orch.current_state):
            self.step_resilient()
            steps += 1
            if crash_after_steps is not None and steps >= crash_after_steps:
                raise RuntimeError(f"simulated_crash_after_{steps}_steps")
        if self._orch.current_state == PRLifecycleState.LEARN.value:
            self._orch._finalize_learn()
        return self._finalize_result()

    def continue_after_crash(self) -> PRLifecycleResult:
        """Resume same runner after simulated crash (checkpoint already loaded)."""
        while not PRLifecycle.is_terminal(self._orch.current_state):
            self.step_resilient()
        if self._orch.current_state == PRLifecycleState.LEARN.value:
            self._orch._finalize_learn()
        return self._finalize_result()

    def _finalize_result(self, error: Optional[str] = None) -> PRLifecycleResult:
        self._orch._scorecard.terminal_state = self._orch.current_state
        err = error
        if err is None and self._orch.current_state == PRLifecycleState.FAILED.value:
            err = self._orch.receipts[-1].evidence.get("error", "failed")
        if err is None and self._orch.current_state == PRLifecycleState.BLOCKED.value:
            err = self._orch.receipts[-1].evidence.get("error", "blocked")
        base = PRLifecycleResult(
            terminal_state=self._orch.current_state,
            run_id=self._orch.run_id,
            pr_number=self._config.base.pr_number,
            branch=self._config.base.branch,
            receipts=[r.to_dict() for r in self._orch.receipts],
            scorecard=self._orch.scorecard.to_dict(),
            context=dict(self._orch.context),
            error=err,
        )
        merged_score = dict(base.scorecard)
        merged_score["resilience"] = self._resilience_score.to_dict()
        merged_score["audit_records"] = self._resilience_score.audit_records
        return PRLifecycleResult(
            terminal_state=base.terminal_state,
            run_id=base.run_id,
            pr_number=base.pr_number,
            branch=base.branch,
            receipts=base.receipts,
            scorecard=merged_score,
            context=base.context,
            error=base.error,
        )


def run_parallel_lifecycles(
    configs: list[ResilienceConfig],
    max_workers: int = 4,
) -> list[PRLifecycleResult]:
    """Run isolated PR lifecycles concurrently (distinct pr_number per config)."""
    results: list[PRLifecycleResult] = []
    lock = threading.Lock()

    def _one(cfg: ResilienceConfig) -> PRLifecycleResult:
        runner = ResilientPRLifecycleRunner(cfg)
        with lock:
            runner.resilience_scorecard.parallel_runs_started += 1
        result = runner.run_to_completion()
        with lock:
            runner.resilience_scorecard.parallel_runs_completed += 1
        return result

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_one, c): c for c in configs}
        for fut in as_completed(futures):
            results.append(fut.result())
    return results


def classify_four_state(tests_passed: bool, live_blocked_reason: str) -> FourStateVerdict:
    """Honest four-state classification for local stress runs."""
    return FourStateVerdict(
        code_complete=True,
        test_verified=tests_passed,
        live_verified=False,
        production_ready=False,
        notes=[
            "CODE_COMPLETE: resilience module present",
            f"TEST_VERIFIED={tests_passed}",
            "LIVE_VERIFIED=False (local SQLite only)",
            "PRODUCTION_READY=False (requires live provider verification)",
            live_blocked_reason,
        ],
    )


def inject_failure_matrix_report() -> list[dict[str, Any]]:
    """Evidence receipt template per boundary for stress documentation."""
    rows = []
    for stage in BOUNDARY_STAGES:
        p = RECOVERY_MATRIX[stage]
        rows.append(
            {
                "boundary": stage,
                "retryable": p.retryable,
                "max_retries": p.max_retries,
                "exhausted_terminal": p.exhausted_terminal,
                "human_escalation": p.human_escalation,
            }
        )
    return rows
