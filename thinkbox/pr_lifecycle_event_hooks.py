"""GitHub PR + CI status event adapters (hermetic fakes) driving PR lifecycle — never auto-merge."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Protocol

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pr_lifecycle import (
    PRLifecycle,
    PRLifecycleConfig,
    PRLifecycleOrchestrator,
    PRLifecycleResult,
    PRLifecycleState,
)
from thinkbox.pr_lifecycle_resilience import ResilienceConfig, ResilientPRLifecycleRunner


class GitHubPRAction(str, Enum):
    OPENED = "opened"
    SYNCHRONIZE = "synchronize"
    REOPENED = "reopened"
    CLOSED = "closed"
    READY_FOR_REVIEW = "ready_for_review"


class CIConclusion(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    PENDING = "pending"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class GitHubPREvent:
    pr_number: int
    branch: str
    action: str
    head_sha: str = ""
    mergeable: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CIStatusEvent:
    pr_number: int
    workflow: str
    conclusion: str
    run_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class PREventSource(Protocol):
    def poll(self) -> list[GitHubPREvent]:
        ...


class CIEventSource(Protocol):
    def poll(self) -> list[CIStatusEvent]:
        ...


class HermeticGitHubPREventSource:
    """In-memory fake GitHub PR webhook stream for tests."""

    def __init__(self) -> None:
        self._queue: list[GitHubPREvent] = []

    def push(self, event: GitHubPREvent) -> None:
        self._queue.append(event)

    def poll(self) -> list[GitHubPREvent]:
        batch = list(self._queue)
        self._queue.clear()
        return batch


class HermeticCIStatusEventSource:
    """In-memory fake CI status stream for tests."""

    def __init__(self) -> None:
        self._queue: list[CIStatusEvent] = []

    def push(self, event: CIStatusEvent) -> None:
        self._queue.append(event)

    def poll(self) -> list[CIStatusEvent]:
        batch = list(self._queue)
        self._queue.clear()
        return batch


@dataclass
class ActiveLifecycleRun:
    pr_number: int
    branch: str
    run_id: str
    runner: ResilientPRLifecycleRunner
    terminal: bool = False
    result: Optional[PRLifecycleResult] = None


class PRLifecycleEventCoordinator:
    """Maps PR/CI events to lifecycle start, resume, or fail — merge is never executed."""

    def __init__(
        self,
        store: OrgMemoryReceiptStore,
        *,
        test_mode: bool = True,
        default_approvals: Optional[dict[str, bool]] = None,
    ) -> None:
        self._store = store
        self._test_mode = test_mode
        self._default_approvals = default_approvals or {"merge": True}
        self._runs_by_pr: dict[int, ActiveLifecycleRun] = {}
        self._merge_attempts: list[dict[str, Any]] = []

    @property
    def merge_attempts(self) -> list[dict[str, Any]]:
        return list(self._merge_attempts)

    def handle_github_event(
        self,
        event: GitHubPREvent,
        *,
        evidence_label: str = "simulated",
    ) -> dict[str, Any]:
        action = event.action.lower()
        if action == GitHubPRAction.CLOSED.value:
            return self._record_external(
                event.pr_number,
                "github_pr_closed",
                {"action": action, "branch": event.branch},
                evidence_label=evidence_label,
            )
        if action in (
            GitHubPRAction.OPENED.value,
            GitHubPRAction.REOPENED.value,
            GitHubPRAction.READY_FOR_REVIEW.value,
        ):
            return self._start_or_resume(
                event.pr_number,
                event.branch,
                source=f"github:{action}",
                evidence_label=evidence_label,
            )
        if action == GitHubPRAction.SYNCHRONIZE.value:
            return self._start_or_resume(
                event.pr_number,
                event.branch,
                source=f"github:{action}",
                evidence_label=evidence_label,
            )
        return {"handled": False, "reason": f"ignored_action:{action}"}

    def handle_ci_event(
        self,
        event: CIStatusEvent,
        *,
        evidence_label: str = "simulated",
    ) -> dict[str, Any]:
        conclusion = event.conclusion.lower()
        active = self._runs_by_pr.get(event.pr_number)
        if active is None:
            return {"handled": False, "reason": "no_active_run"}

        self._store.append_lifecycle(
            run_id=active.run_id,
            pr_number=event.pr_number,
            branch=active.branch,
            from_state=active.runner.orchestrator.current_state,
            to_state=active.runner.orchestrator.current_state,
            action="ci_status_observed",
            result="success",
            evidence={
                "workflow": event.workflow,
                "conclusion": conclusion,
                "ci_run_id": event.run_id,
            },
            evidence_label=evidence_label,
        )

        if conclusion == CIConclusion.FAILURE.value:
            return self._fail_active(
                event.pr_number,
                f"ci_failure:{event.workflow}",
                evidence_label=evidence_label,
            )
        if conclusion == CIConclusion.SUCCESS.value:
            return self._resume_active(
                event.pr_number,
                source=f"ci_success:{event.workflow}",
                evidence_label=evidence_label,
            )
        return {"handled": True, "action": "ci_pending_noop", "conclusion": conclusion}

    def request_merge(self, pr_number: int) -> dict[str, Any]:
        """Explicit merge requests are recorded and denied (founder gate)."""
        self._merge_attempts.append({"pr_number": pr_number, "denied": True})
        active = self._runs_by_pr.get(pr_number)
        run_id = active.run_id if active else f"no_run_{pr_number}"
        branch = active.branch if active else ""
        self._store.append_lifecycle(
            run_id=run_id,
            pr_number=pr_number,
            branch=branch,
            from_state="READY_FOR_CLOSE",
            to_state="READY_FOR_CLOSE",
            action="merge_requested",
            result="blocked",
            evidence={"auto_merge": False, "reason": "founder_approval_required"},
        )
        return {"merged": False, "auto_merge": False, "reason": "founder_approval_required"}

    def drain_sources(
        self,
        github: PREventSource,
        ci: CIEventSource,
    ) -> list[dict[str, Any]]:
        outcomes: list[dict[str, Any]] = []
        for ev in github.poll():
            outcomes.append(self.handle_github_event(ev))
        for ev in ci.poll():
            outcomes.append(self.handle_ci_event(ev))
        return outcomes

    def _start_or_resume(
        self,
        pr_number: int,
        branch: str,
        source: str,
        *,
        evidence_label: str = "simulated",
    ) -> dict[str, Any]:
        active = self._runs_by_pr.get(pr_number)
        if active and not active.terminal:
            return self._resume_active(pr_number, source=source, evidence_label=evidence_label)

        cfg = PRLifecycleConfig(
            pr_number=pr_number,
            branch=branch,
            test_mode=self._test_mode,
            approvals=dict(self._default_approvals),
        )
        r_cfg = ResilienceConfig(base=cfg, checkpoint_dir=None)
        runner = OrgMemoryResilientRunner(r_cfg, self._store)
        active = ActiveLifecycleRun(
            pr_number=pr_number,
            branch=branch,
            run_id=runner.orchestrator.run_id,
            runner=runner,
        )
        self._runs_by_pr[pr_number] = active
        self._store.append_lifecycle(
            run_id=active.run_id,
            pr_number=pr_number,
            branch=branch,
            from_state=PRLifecycleState.PR_CREATED.value,
            to_state=PRLifecycleState.PR_CREATED.value,
            action="lifecycle_start",
            result="success",
            evidence={"source": source},
            evidence_label=evidence_label,
        )
        active.runner.step_resilient()
        return {"handled": True, "action": "started", "run_id": active.run_id}

    def _resume_active(
        self,
        pr_number: int,
        source: str,
        *,
        evidence_label: str = "simulated",
    ) -> dict[str, Any]:
        active = self._runs_by_pr.get(pr_number)
        if active is None:
            return {"handled": False, "reason": "no_active_run"}
        if active.terminal:
            return {"handled": True, "action": "already_terminal", "state": active.result.terminal_state if active.result else ""}

        while not PRLifecycle.is_terminal(active.runner.orchestrator.current_state):
            active.runner.step_resilient()
            if active.runner.orchestrator.current_state == PRLifecycleState.LEARN.value:
                active.runner.orchestrator._finalize_learn()
                break
        active.terminal = True
        active.result = active.runner._finalize_result()
        return {
            "handled": True,
            "action": "resumed_to_terminal",
            "source": source,
            "terminal_state": active.result.terminal_state,
            "run_id": active.run_id,
        }

    def _fail_active(
        self,
        pr_number: int,
        reason: str,
        *,
        evidence_label: str = "simulated",
    ) -> dict[str, Any]:
        active = self._runs_by_pr.get(pr_number)
        if active is None:
            return {"handled": False, "reason": "no_active_run"}
        state = active.runner.orchestrator.current_state
        active.runner.orchestrator._fail(state, "ci_failure", reason, {"source": "ci"})
        active.terminal = True
        active.result = active.runner._finalize_result(error=reason)
        return {"handled": True, "action": "failed", "reason": reason, "run_id": active.run_id}

    def _record_external(
        self,
        pr_number: int,
        action: str,
        evidence: dict[str, Any],
        *,
        evidence_label: str = "simulated",
    ) -> dict[str, Any]:
        run_id = (
            self._runs_by_pr[pr_number].run_id if pr_number in self._runs_by_pr else f"external_{pr_number}"
        )
        self._store.append_lifecycle(
            run_id=run_id,
            pr_number=pr_number,
            branch=evidence.get("branch", ""),
            from_state="EXTERNAL",
            to_state="EXTERNAL",
            action=action,
            result="success",
            evidence=evidence,
            evidence_label=evidence_label,
        )
        return {"handled": True, "action": action}


class OrgMemoryResilientRunner(ResilientPRLifecycleRunner):
    """Resilient runner that dual-writes checkpoints and receipts to org memory."""

    def __init__(self, config: ResilienceConfig, org_store: OrgMemoryReceiptStore) -> None:
        super().__init__(config)
        self._org_store = org_store

    @classmethod
    def resume_from_org_memory(
        cls,
        config: ResilienceConfig,
        org_store: OrgMemoryReceiptStore,
        run_id: str,
    ) -> "OrgMemoryResilientRunner":
        snapshot = org_store.load_checkpoint(run_id)
        if snapshot is None:
            raise ValueError(f"No org-memory checkpoint for run_id={run_id}")
        runner = cls(config, org_store)
        runner._orch.restore_snapshot(snapshot)
        runner._resilience_score.crash_resumes += 1
        runner._prev_context = dict(runner._orch.context)
        return runner

    def _checkpoint(self) -> None:
        super()._checkpoint()
        snap = self._orch.snapshot()
        self._org_store.save_checkpoint(
            self._orch.run_id,
            self._config.base.pr_number,
            self._config.base.branch,
            snap,
        )

    def step_resilient(self) -> dict[str, Any]:
        out = super().step_resilient()
        receipt = out.get("receipt") or {}
        if receipt:
            self._org_store.append_lifecycle(
                run_id=receipt.get("run_id", self._orch.run_id),
                pr_number=receipt.get("pr_number", self._config.base.pr_number),
                branch=receipt.get("branch", self._config.base.branch),
                from_state=receipt.get("from_state", ""),
                to_state=receipt.get("to_state", ""),
                action=receipt.get("action", ""),
                result=receipt.get("result", ""),
                evidence=receipt.get("evidence"),
                experiment_id=self._orch.context.get("experiment_id"),
            )
        return out
