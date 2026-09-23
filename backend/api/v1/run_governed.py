"""Governed ``POST /api/v1/run`` admission, engine wiring, and background execution (PR #132)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from fastapi import HTTPException

from thinkbox.admission import AdmissionDecision
from thinkbox.dashboard_state import (
    DashboardCategory,
    DashboardEvent,
    ThinkJobEntry,
    get_dashboard_state,
)
from thinkbox.engine import EngineConfig, ThinkBoxEngine
from thinkbox.governed import GovernedEngine, GovernedEngineConfig
from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.hermetic_provider import HermeticModelProvider, provider_complete_async
from thinkbox.identity import IdentityLedger
from thinkbox.model_client import ModelConfig

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
) -> ApiRunGovernance:
    """Replace singleton (unittest isolation)."""
    global _api_governance
    _api_governance = ApiRunGovernance(
        token_service=GovernanceTokenService(signing_key=signing_key),
        identity_ledger=IdentityLedger(),
        ledger_path=ledger_path,
    )
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


async def execute_governed_run_background(
    governed: GovernedEngine,
    ctx: RunAdmissionContext,
    goal: str,
    job_entry: ThinkJobEntry,
    *,
    complete_async: CompleteAsyncFn | None = None,
) -> None:
    dashboard = get_dashboard_state()
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
            job_entry.result = {"error": result.get("reason", "governance_denied")}
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
        dashboard.upsert_think_job(job_entry)
        await dashboard.emit(
            DashboardCategory.THINK_JOBS,
            DashboardEvent.TASK_COMPLETED,
            job_entry.model_dump(),
            "governed_engine",
        )
    except Exception as exc:
        job_entry.status = "failed"
        job_entry.result = {"error": str(exc)}
        dashboard.upsert_think_job(job_entry)
        await dashboard.emit(
            DashboardCategory.THINK_JOBS,
            DashboardEvent.TASK_FAILED,
            job_entry.model_dump(),
            "governed_engine",
        )
