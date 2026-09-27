"""Governed ``POST /api/v1/run`` admission, engine wiring, and background execution (PR #132–#133)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

from fastapi import HTTPException

from backend.api.v1.run_receipts import (
    HttpRunReceiptBinding,
    RunReceiptPersistError,
    apply_persist_failure,
    begin_http_run_receipt,
    emit_receipt_dashboard,
    finalize_http_run_receipt,
    get_http_run_persistence,
    persist_profile_for_http,
    reset_http_run_persistence_for_tests,
    write_simple_http_run_proof,
    receipt_persistence_snapshot,
)
from thinkbox.admission import AdmissionDecision
from thinkbox.dashboard_state import (
    DashboardCategory,
    DashboardEvent,
    ThinkJobEntry,
    get_dashboard_state,
)
from thinkbox.governed_execution_lifecycle import (
    PHASE_ADMISSION,
    PHASE_COMPLETED,
    PHASE_FAILED,
    PHASE_QUEUED,
    PHASE_RUNNING,
    open_lifecycle_repo,
    persist_lifecycle_phase,
)
from thinkbox.engine import EngineConfig, ThinkBoxEngine
from thinkbox.governed import GovernedEngine, GovernedEngineConfig
from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.hermetic_provider import HermeticModelProvider, provider_complete_async
from thinkbox.identity import IdentityLedger
HERMETIC_MODEL_ID = "hermetic-mock"
DEFAULT_RUN_CAPABILITY = "goal:execute"
DEFAULT_VERIFIED_CAPABILITY = "goal:execute:verified"

CompleteAsyncFn = Callable[[str], Awaitable[str | tuple[str, dict[str, int]]]]


@dataclass
class RunAdmissionContext:
    """Parsed governance fields for one HTTP run request."""

    agent_id: str
    token_value: str
    capability: str
    verified: bool
    subtasks: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ApiRunGovernance:
    """Shared token service + identity ledger for all API runs (singleton)."""

    token_service: GovernanceTokenService
    identity_ledger: IdentityLedger
    ledger_path: str = ":memory:"
    _admission_governed: GovernedEngine | None = field(default=None, repr=False)

    def admission_governed(self) -> GovernedEngine:
        """Reuse one governed shell so HTTP admission shares the run ledger file."""
        if self._admission_governed is None:
            self._admission_governed = self.build_governed_engine(ThinkBoxEngine(EngineConfig()))
        return self._admission_governed

    def register_agent(self, agent_id: str, capabilities: list[str]) -> str:
        self.identity_ledger.register(agent_id=agent_id, capabilities=capabilities)
        token = self.token_service.issue(
            TokenRequest(agent_id=agent_id, capabilities=capabilities, ttl_seconds=3600.0)
        )
        return token.token_value

    def admit_http_run(self, ctx: RunAdmissionContext) -> AdmissionDecision:
        governed = self.admission_governed()
        if not ctx.token_value.strip():
            decision = governed.authorize(
                "",
                ctx.agent_id,
                ctx.capability,
                "http_run_admission",
                metadata={"surface": "http", "phase": "pre_execute"},
            )
            return decision
        return governed.authorize(
            ctx.token_value,
            ctx.agent_id,
            ctx.capability,
            "http_run_admission",
            metadata={"surface": "http", "phase": "pre_execute", "verified": ctx.verified},
        )

    def build_governed_engine(self, base: ThinkBoxEngine) -> GovernedEngine:
        return GovernedEngine(
            GovernedEngineConfig(
                engine=base,
                token_service=self.token_service,
                identity_ledger=self.identity_ledger,
                ledger_path=self.ledger_path,
            )
        )

_api_governance: ApiRunGovernance | None = None
_complete_async_override: CompleteAsyncFn | None = None


def get_api_run_governance() -> ApiRunGovernance:
    global _api_governance
    if _api_governance is None:
        signing_key = os.environ.get("THINKBOX_GOVERNANCE_SIGNING_KEY") or "hermetic-api-run-signing"
        _api_governance = ApiRunGovernance(
            token_service=GovernanceTokenService(signing_key=signing_key),
            identity_ledger=IdentityLedger(),
        )
    return _api_governance


def reset_api_run_governance_for_tests(
    *,
    signing_key: str = "hermetic-test-signing",
    ledger_path: str = ":memory:",
    reset_receipts: bool = True,
) -> ApiRunGovernance:
    """Replace singleton (unittest isolation)."""
    global _api_governance
    _api_governance = ApiRunGovernance(
        token_service=GovernanceTokenService(signing_key=signing_key),
        identity_ledger=IdentityLedger(),
        ledger_path=ledger_path,
    )
    if reset_receipts:
        reset_http_run_persistence_for_tests()
    return _api_governance


def set_complete_async_override(fn: CompleteAsyncFn | None) -> None:
    """Test hook: inject ``complete_async`` for verified runs without Mercury."""
    global _complete_async_override
    _complete_async_override = fn


def validate_verified_subtasks(subtasks: list[dict[str, Any]]) -> None:
    """Fail-fast shape check for F023 subtask specs before admission."""
    if not subtasks:
        raise HTTPException(
            status_code=422,
            detail={"error": "verified_run_requires_subtasks"},
        )
    for index, st in enumerate(subtasks):
        missing = [k for k in ("description", "family", "spec") if k not in st]
        if missing:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "invalid_subtask_shape",
                    "index": index,
                    "missing": missing,
                },
            )
        if not isinstance(st.get("spec"), dict):
            raise HTTPException(
                status_code=422,
                detail={"error": "invalid_subtask_spec", "index": index},
            )


def parse_run_admission(
    *,
    agent_id: str | None,
    governance_token: str | None,
    header_token: str | None,
    header_capability: str | None,
    capability: str | None,
    verified: bool,
    subtasks: list[dict[str, Any]] | None,
) -> RunAdmissionContext:
    token_value = (governance_token or header_token or "").strip()
    cap = (capability or header_capability or "").strip()
    if verified:
        cap = cap or DEFAULT_VERIFIED_CAPABILITY
    else:
        cap = cap or DEFAULT_RUN_CAPABILITY
    return RunAdmissionContext(
        agent_id=(agent_id or "api-run-agent").strip() or "api-run-agent",
        token_value=token_value,
        capability=cap,
        verified=verified,
        subtasks=list(subtasks or []),
    )


def governance_status_snapshot() -> dict[str, Any]:
    """Redacted read-only status for hermetic ops (no token values)."""
    gov = get_api_run_governance()
    shell = gov.admission_governed()
    entries = list(shell.ledger.entries())
    stack = get_http_run_persistence()
    recent = stack.manager.db.restart_recovery()
    receipt_snap = receipt_persistence_snapshot()
    from backend.api.v1.run_job_status import job_status_snapshot_for_governance

    job_snap = job_status_snapshot_for_governance()
    return {
        "surface": "http",
        "default_capability": DEFAULT_RUN_CAPABILITY,
        "verified_capability": DEFAULT_VERIFIED_CAPABILITY,
        "hermetic_model_id": HERMETIC_MODEL_ID,
        "identities_registered": len(gov.identity_ledger.list()),
        "tokens_issued": gov.token_service.issued_count(),
        "ledger_entries": len(entries),
        "ledger_verified": shell.ledger.verify(),
        "ledger_path_kind": "memory" if gov.ledger_path == ":memory:" else "file",
        "receipt_db_path_kind": "file" if stack.db_path != ":memory:" else "memory",
        "receipt_recent_experiments": len(recent.get("recent_experiments", [])),
        "receipt_persistence": "enabled",
        "receipt_snapshot": receipt_snap,
        "think_job_status": job_snap,
    }


def require_http_admission(ctx: RunAdmissionContext) -> AdmissionDecision:
    """Fail-closed synchronous admission before background work starts."""
    gov = get_api_run_governance()
    decision = gov.admit_http_run(ctx)
    if not decision.allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "governance_denied",
                "reason": decision.reason,
                "agent_id": ctx.agent_id,
                "capability": ctx.capability,
            },
        )
    return decision


def build_complete_async_for_run(
    model: str | None,
    subtasks: list[dict[str, Any]],
) -> CompleteAsyncFn | None:
    if _complete_async_override is not None:
        return _complete_async_override
    if model == HERMETIC_MODEL_ID and subtasks:
        provider = HermeticModelProvider(subtasks)
        return provider_complete_async(provider)
    return None


def persist_http_run_lifecycle(
    worktree: str,
    job_entry: ThinkJobEntry,
    phase: str,
    *,
    execution_substrate: str = "",
    adapter_provider: str = "",
    checkpoint_id: str = "",
    artifact_path: str = "",
    artifact_hash: str = "",
    verdict: str = "",
    http_proof_path: str = "",
    result: dict[str, Any] | None = None,
) -> None:
    """Write one lifecycle transition to the existing Repository job store."""
    persist_lifecycle_phase(
        open_lifecycle_repo(worktree),
        job_entry.job_id,
        phase,
        goal=job_entry.goal,
        receipt_id=job_entry.receipt_id,
        experiment_id=job_entry.experiment_id,
        session_id=job_entry.session_id,
        execution_substrate=execution_substrate,
        adapter_provider=adapter_provider,
        checkpoint_id=checkpoint_id,
        artifact_path=artifact_path,
        artifact_hash=artifact_hash,
        verdict=verdict,
        http_proof_path=http_proof_path,
        result=result,
    )


def resume_http_queued_job(
    job_id: str,
    *,
    exec_command: str | None = None,
    worktree: str | None = None,
) -> Any:
    """Operator QUEUED resume: reuse the existing receipt; never open a second one."""
    from thinkbox.governed_execution_lifecycle import lifecycle_worktree_path
    from thinkbox.lifecycle_resume import QueuedResumeResult, resume_queued_job

    repo = open_lifecycle_repo(worktree or lifecycle_worktree_path())
    result: QueuedResumeResult = resume_queued_job(repo, job_id, exec_command=exec_command)
    return result


def admit_and_queue_http_run(
    job_entry: ThinkJobEntry,
    *,
    worktree: str,
    execution_substrate: str = "",
) -> None:
    """Persist ADMISSION then QUEUED before background execution starts."""
    persist_http_run_lifecycle(
        worktree,
        job_entry,
        PHASE_ADMISSION,
        execution_substrate=execution_substrate,
    )
    persist_http_run_lifecycle(
        worktree,
        job_entry,
        PHASE_QUEUED,
        execution_substrate=execution_substrate,
    )


async def execute_governed_shell_background(
    ctx: RunAdmissionContext,
    job_entry: ThinkJobEntry,
    *,
    execution_substrate: str,
    exec_command: str,
    receipt_binding: HttpRunReceiptBinding | None = None,
    worktree: str = ".",
) -> None:
    """Explicit substrate shell execution (local or configured remote only)."""
    from pathlib import Path

    from thinkbox.governed_job_execution import (
        GovernedJobExecutionError,
        execute_governed_job_command,
    )
    from thinkbox.repository import Repository

    dashboard = get_dashboard_state()
    stack = get_http_run_persistence()
    binding = receipt_binding
    persist_http_run_lifecycle(
        worktree,
        job_entry,
        PHASE_RUNNING,
        execution_substrate=execution_substrate,
    )
    job_entry.phase = PHASE_RUNNING
    dashboard.upsert_think_job(job_entry)
    try:
        result = execute_governed_job_command(
            substrate=execution_substrate,
            job_id=job_entry.job_id,
            command=exec_command,
            repo=Repository(Path(worktree)),
        )
    except GovernedJobExecutionError as exc:
        job_entry.status = "failed"
        job_entry.phase = PHASE_FAILED
        job_entry.result = {"error": exc.code, "message": str(exc)}
        persist_http_run_lifecycle(
            worktree,
            job_entry,
            PHASE_FAILED,
            execution_substrate=execution_substrate,
            verdict=exc.code,
            result=job_entry.result,
        )
        if binding:
            finalize_http_run_receipt(
                binding,
                status="failed",
                outcome=job_entry.result,
                confidence=0.0,
                persistence=stack,
            )
        dashboard.upsert_think_job(job_entry)
        await dashboard.emit(
            DashboardCategory.THINK_JOBS,
            DashboardEvent.TASK_FAILED,
            job_entry.model_dump(),
            "governed_shell",
        )
        return

    receipt = result.receipt
    proof = result.public_proof
    succeeded = receipt.status == "COMPLETED" and receipt.verified
    job_entry.status = "completed" if succeeded else "failed"
    job_entry.progress = 1.0 if succeeded else 0.0
    job_entry.tasks_total = 1
    job_entry.tasks_completed = 1 if succeeded else 0
    job_entry.phase = "completed" if succeeded else "failed"
    job_entry.result = {
        "governed": True,
        "governed_shell": True,
        "execution_substrate": result.substrate,
        "adapter_provider": result.adapter_provider,
        "execution_proof": proof,
        "capability": ctx.capability,
        "agent_id": ctx.agent_id,
    }
    job_entry.evidence_label = "verified"
    http_proof_path = ""
    if binding:
        proof_path, proof_sha = write_simple_http_run_proof(
            binding,
            job_entry.result,
            persistence=stack,
        )
        http_proof_path = proof_path
        finalize_http_run_receipt(
            binding,
            status="completed" if succeeded else "failed",
            outcome=job_entry.result,
            confidence=1.0 if succeeded else 0.0,
            proof_path=proof_path,
            proof_sha256=proof_sha,
            persistence=stack,
        )
        job_entry.receipt_id = binding.receipt_id
        job_entry.experiment_id = binding.experiment_id
        job_entry.session_id = binding.session_id
        await emit_receipt_dashboard(
            binding,
            status="completed" if succeeded else "failed",
            proof_path=proof_path,
        )
    persist_http_run_lifecycle(
        worktree,
        job_entry,
        PHASE_COMPLETED if succeeded else PHASE_FAILED,
        execution_substrate=result.substrate,
        adapter_provider=result.adapter_provider,
        checkpoint_id=receipt.checkpoint_id,
        artifact_path=receipt.artifact_path,
        artifact_hash=receipt.artifact_hash,
        verdict=receipt.status,
        http_proof_path=http_proof_path,
        result=job_entry.result,
    )
    job_entry.completed_at = datetime.now(timezone.utc).isoformat()
    dashboard.upsert_think_job(job_entry)
    await dashboard.emit(
        DashboardCategory.THINK_JOBS,
        DashboardEvent.TASK_COMPLETED if succeeded else DashboardEvent.TASK_FAILED,
        job_entry.model_dump(),
        "governed_shell",
    )


async def execute_governed_run_background(
    governed: GovernedEngine,
    ctx: RunAdmissionContext,
    goal: str,
    job_entry: ThinkJobEntry,
    *,
    complete_async: CompleteAsyncFn | None = None,
    receipt_binding: HttpRunReceiptBinding | None = None,
    execution_substrate: str | None = None,
    exec_command: str | None = None,
    worktree: str = ".",
) -> None:
    dashboard = get_dashboard_state()
    stack = get_http_run_persistence()
    binding = receipt_binding
    persist_http_run_lifecycle(
        worktree,
        job_entry,
        PHASE_RUNNING,
        execution_substrate=execution_substrate or "",
    )
    job_entry.phase = PHASE_RUNNING
    dashboard.upsert_think_job(job_entry)
    if execution_substrate and exec_command:
        await execute_governed_shell_background(
            ctx,
            job_entry,
            execution_substrate=execution_substrate,
            exec_command=exec_command,
            receipt_binding=binding,
            worktree=worktree,
        )
        return
    try:
        if ctx.verified and ctx.subtasks:
            if complete_async is None:
                raise ValueError("verified run requires complete_async or hermetic-mock subtasks")
            result = await governed.execute_verified_goal(
                goal,
                ctx.subtasks,
                complete_async,
                token_value=ctx.token_value,
                agent_id=ctx.agent_id,
                capability=ctx.capability,
                emit_dashboard=True,
                manager=stack.manager,
                persist_profile=persist_profile_for_http(ctx.agent_id),
                goal_experiment_id=binding.experiment_id if binding else None,
                session_id_override=binding.session_id if binding else None,
            )
        else:
            result = await governed.execute_goal(
                goal,
                token_value=ctx.token_value,
                agent_id=ctx.agent_id,
                capability=ctx.capability,
            )
        if result.get("governed") is False:
            job_entry.status = "failed"
            job_entry.phase = PHASE_FAILED
            job_entry.result = {"error": result.get("reason", "governance_denied")}
            persist_http_run_lifecycle(
                worktree,
                job_entry,
                PHASE_FAILED,
                verdict=str(job_entry.result.get("error") or "governance_denied"),
                result=job_entry.result,
            )
            if binding:
                try:
                    finalize_http_run_receipt(
                        binding,
                        status="failed",
                        outcome=job_entry.result,
                        confidence=0.0,
                        persistence=stack,
                    )
                    await emit_receipt_dashboard(binding, status="failed")
                except RunReceiptPersistError as persist_exc:
                    await apply_persist_failure(job_entry, binding, persist_exc)
                    return
            dashboard.upsert_think_job(job_entry)
            await dashboard.emit(
                DashboardCategory.THINK_JOBS,
                DashboardEvent.TASK_FAILED,
                job_entry.model_dump(),
                "governed_engine",
            )
            return
        job_entry.status = "completed"
        job_entry.progress = 1.0
        verified = result.get("verified") or {}
        job_entry.tasks_total = result.get("total_tasks") or verified.get("tasks_total") or len(ctx.subtasks)
        job_entry.tasks_completed = result.get("completed") or verified.get("tasks_succeeded") or job_entry.tasks_total
        job_entry.result = result
        job_entry.phase = "completed"
        if binding:
            binding.metadata["goal_experiment_id"] = result.get("goal_experiment_id", binding.experiment_id)
            proof_path = result.get("proof_artifact")
            proof_sha = result.get("proof_sha256")
            if not proof_path:
                proof_path, proof_sha = write_simple_http_run_proof(binding, result, persistence=stack)
            try:
                finalize_http_run_receipt(
                    binding,
                    status="completed",
                    outcome={
                        "governed": True,
                        "verified": ctx.verified,
                        "capability": ctx.capability,
                        "agent_id": ctx.agent_id,
                        "summary": {
                            k: result.get(k)
                            for k in (
                                "total_tasks",
                                "completed",
                                "goal_experiment_id",
                                "session_id",
                                "verification_rate",
                                "calls_spent",
                            )
                        },
                    },
                    confidence=float(verified.get("verification_rate", 1.0) or 1.0),
                    proof_path=proof_path,
                    proof_sha256=proof_sha,
                    persistence=stack,
                )
                result["receipt_id"] = binding.receipt_id
                result["experiment_id"] = binding.experiment_id
                result["session_id"] = binding.session_id
                job_entry.receipt_id = binding.receipt_id
                job_entry.experiment_id = binding.experiment_id
                job_entry.session_id = binding.session_id
                job_entry.result = result
                await emit_receipt_dashboard(binding, status="completed", proof_path=proof_path)
            except RunReceiptPersistError as persist_exc:
                await apply_persist_failure(job_entry, binding, persist_exc)
                return
        job_entry.completed_at = datetime.now(timezone.utc).isoformat()
        persist_http_run_lifecycle(
            worktree,
            job_entry,
            PHASE_COMPLETED,
            http_proof_path=str((job_entry.result or {}).get("proof_artifact") or ""),
            verdict="COMPLETED",
            result=job_entry.result if isinstance(job_entry.result, dict) else {},
        )
        dashboard.upsert_think_job(job_entry)
        completed_payload = job_entry.model_dump()
        if binding:
            from backend.api.v1.run_job_status import build_receipt_link_card

            completed_payload["receipt_card"] = build_receipt_link_card(
                job_id=job_entry.job_id,
                status=job_entry.status,
                phase=job_entry.phase,
                receipt_id=job_entry.receipt_id,
                experiment_id=job_entry.experiment_id,
                session_id=job_entry.session_id,
                proof_artifact=str((job_entry.result or {}).get("proof_artifact") or ""),
                tasks_total=job_entry.tasks_total,
                tasks_completed=job_entry.tasks_completed,
            )
        await dashboard.emit(
            DashboardCategory.THINK_JOBS,
            DashboardEvent.TASK_COMPLETED,
            completed_payload,
            "governed_engine",
        )
    except Exception as exc:
        job_entry.status = "failed"
        job_entry.phase = PHASE_FAILED
        job_entry.result = {"error": str(exc)}
        persist_http_run_lifecycle(
            worktree,
            job_entry,
            PHASE_FAILED,
            verdict="exception",
            result=job_entry.result,
        )
        if binding:
            try:
                finalize_http_run_receipt(
                    binding,
                    status="failed",
                    outcome=job_entry.result,
                    confidence=0.0,
                    persistence=stack,
                )
            except RunReceiptPersistError as persist_exc:
                await apply_persist_failure(job_entry, binding, persist_exc)
                return
        dashboard.upsert_think_job(job_entry)
        await dashboard.emit(
            DashboardCategory.THINK_JOBS,
            DashboardEvent.TASK_FAILED,
            job_entry.model_dump(),
            "governed_engine",
        )


def open_http_run_receipt(
    *,
    engine_id: str,
    goal: str,
    agent_id: str,
    verified: bool,
    capability: str,
    admission_reason: str,
) -> HttpRunReceiptBinding:
    return begin_http_run_receipt(
        engine_id=engine_id,
        goal=goal,
        agent_id=agent_id,
        verified=verified,
        capability=capability,
        admission_reason=admission_reason,
    )
