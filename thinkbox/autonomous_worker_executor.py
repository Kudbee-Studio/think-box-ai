"""Hermetic Trait Lab autonomous worker executor (L01–L25).

Governance layer that composes CloudExecutionWorker with K01–K25 Integration Major quality gate.
No live APIs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from core.memory.store import MemoryStore
from thinkbox.autonomous_integration_major import (
    export_trait_lab_autonomous_integration_major_report,
    open_trait_lab_autonomous_integration_major,
    require_trait_lab_autonomous_integration_major_no_live_ack,
    require_trait_lab_autonomous_integration_major_provenance,
    verify_trait_lab_autonomous_integration_major_report,
)
from thinkbox.cloud_execution.durable_engine import DurableCloudExecutionEngine
from thinkbox.cloud_execution.queue import ExecutionJobQueue
from thinkbox.cloud_execution.worker_orchestrator import CloudExecutionWorker
from thinkbox.memory_layers import MemoryLayerError, record_task_step, write_verified

_WORKER_KIND = "trait-lab-autonomous-worker-executor"
_REPORT_KIND = "trait-lab-autonomous-worker-executor-report"
_FACT_PREFIX = "trait-lab-auto-worker-exec-"

TRAIT_LAB_AUTONOMOUS_WORKER_EXECUTOR_OPS: tuple[str, ...] = (
    "refuse_live",
    "require_provenance",
    "require_no_live_ack",
    "plan_worker",
    "validate_worker_plan",
    "sign_worker_plan",
    "verify_worker_plan",
    "list_gate_modes",
    "gate_mode_ok",
    "run_worker_cycle",
    "run_worker_continuous",
    "export_worker_report",
    "verify_worker_report",
    "assert_worker_ok",
    "worker_status",
    "worker_digest",
    "worker_etag",
    "public_worker_row",
    "manifest_worker_config",
    "bundle_worker_for_ci",
    "compare_worker_reports",
    "worker_row",
    "persist_worker_artifact",
    "worker_contract_summary",
    "open_worker_executor",
)

TRAIT_LAB_AUTONOMOUS_WORKER_GATE_MODES: tuple[str, ...] = ("gate", "gate_regression")


def refuse_trait_lab_autonomous_worker_executor_live(payload: Any) -> None:
    """L01 — worker payloads may not claim LIVE VERIFIED."""
    if isinstance(payload, dict) and payload.get("live_verified") is True:
        raise MemoryLayerError(
            "live_claim",
            "autonomous worker executor may not claim LIVE VERIFIED",
        )


def require_trait_lab_autonomous_worker_executor_provenance(*, agent_id: str, task_id: str) -> dict[str, Any]:
    """L02 — fail-closed without agent_id and task_id."""
    return require_trait_lab_autonomous_integration_major_provenance(agent_id=agent_id, task_id=task_id)


def require_trait_lab_autonomous_worker_executor_no_live_ack(environ: Any = None) -> dict[str, Any]:
    """L03 — fail-closed when swarm live ack is present."""
    return require_trait_lab_autonomous_integration_major_no_live_ack(environ)


def _worker_body(
    *,
    gate_mode: str,
    queue: str,
    max_claims: int,
    budget: int,
    worker_id: str,
) -> dict[str, Any]:
    return {
        "kind": _WORKER_KIND,
        "gate_mode": gate_mode,
        "queue": queue,
        "max_claims": max_claims,
        "budget": budget,
        "worker_id": worker_id,
        "live_verified": False,
    }


def _require_gate_mode(mode: Any) -> str:
    wanted = str(mode or "").strip()
    if wanted not in TRAIT_LAB_AUTONOMOUS_WORKER_GATE_MODES:
        raise MemoryLayerError("invalid_mode", f"unknown worker gate mode {wanted or '<empty>'}")
    return wanted


def plan_trait_lab_autonomous_worker_executor(
    *,
    queue: str = "",
    gate_mode: str = "gate_regression",
    max_claims: int = 10,
    budget: int = 100,
    worker_id: str = "trait-lab-worker-1",
) -> dict[str, Any]:
    """L04 — unsigned worker plan."""
    mode = _require_gate_mode(gate_mode)
    body = _worker_body(
        gate_mode=mode,
        queue=queue,
        max_claims=max_claims,
        budget=budget,
        worker_id=worker_id,
    )
    refuse_trait_lab_autonomous_worker_executor_live(body)
    return body


def validate_trait_lab_autonomous_worker_executor(plan: Any) -> dict[str, Any]:
    """L05 — fail-closed validation."""
    if not isinstance(plan, dict):
        raise MemoryLayerError("invalid_worker", "worker plan must be an object")
    refuse_trait_lab_autonomous_worker_executor_live(plan)
    if plan.get("kind") not in {None, _WORKER_KIND}:
        raise MemoryLayerError("invalid_worker", "kind must be trait-lab-autonomous-worker-executor")
    mode = _require_gate_mode(plan.get("gate_mode"))
    queue = str(plan.get("queue") or "").strip()
    max_claims = int(plan.get("max_claims") or 10)
    budget = int(plan.get("budget") or 100)
    worker_id = str(plan.get("worker_id") or "trait-lab-worker-1").strip()
    if max_claims <= 0:
        raise MemoryLayerError("invalid_worker", "max_claims must be positive")
    if budget <= 0:
        raise MemoryLayerError("invalid_worker", "budget must be positive")
    return {**_worker_body(
        gate_mode=mode,
        queue=queue,
        max_claims=max_claims,
        budget=budget,
        worker_id=worker_id,
    ), "valid": True}


def sign_trait_lab_autonomous_worker_executor(plan: Any) -> dict[str, Any]:
    """L06 — sign worker plan."""
    validated = validate_trait_lab_autonomous_worker_executor(plan)
    body = _worker_body(
        gate_mode=validated["gate_mode"],
        queue=validated["queue"],
        max_claims=validated["max_claims"],
        budget=validated["budget"],
        worker_id=validated["worker_id"],
    )
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**body, "worker_sha256": hashlib.sha256(encoded).hexdigest(), "live_verified": False}


def verify_trait_lab_autonomous_worker_executor(plan: Any) -> dict[str, Any]:
    """L07 — rematch worker_sha256."""
    if not isinstance(plan, dict):
        raise MemoryLayerError("invalid_worker", "worker plan must be an object")
    if plan.get("kind") != _WORKER_KIND:
        raise MemoryLayerError("invalid_worker", "kind must be trait-lab-autonomous-worker-executor")
    refuse_trait_lab_autonomous_worker_executor_live(plan)
    mode = _require_gate_mode(plan.get("gate_mode"))
    sha = str(plan.get("worker_sha256") or "").strip().lower()
    if len(sha) != 64:
        raise MemoryLayerError("missing_worker_hash", "verify requires worker_sha256")
    body = _worker_body(
        gate_mode=mode,
        queue=str(plan.get("queue") or ""),
        max_claims=int(plan.get("max_claims") or 10),
        budget=int(plan.get("budget") or 100),
        worker_id=str(plan.get("worker_id") or "trait-lab-worker-1"),
    )
    got = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if got != sha:
        raise MemoryLayerError("worker_mismatch", f"worker hashed {got[:12]} not {sha[:12]}")
    return {**body, "matched": True, "worker_sha256": sha, "live_verified": False}


def list_trait_lab_autonomous_worker_gate_modes(plan: Any) -> list[str]:
    """L08 — available gate modes from signed plan."""
    signed = verify_trait_lab_autonomous_worker_executor(plan)
    return list(TRAIT_LAB_AUTONOMOUS_WORKER_GATE_MODES)


def trait_lab_autonomous_worker_gate_mode_ok(run: Any, mode: str) -> bool:
    """L09 — true when named gate mode result is ok."""
    wanted = str(mode or "").strip()
    for row in run.get("cycle_results") or []:
        if isinstance(row, dict) and row.get("gate_mode") == wanted:
            return bool(row.get("ok"))
    return False


def _run_integration_gate(
    *,
    agent_id: str,
    task_id: str,
    environ: Any,
    gate_mode: str,
) -> dict[str, Any]:
    """Run Integration Major gate."""
    return open_trait_lab_autonomous_integration_major(
        agent_id=agent_id,
        task_id=f"{task_id}:integration",
        environ=environ,
        mode=gate_mode,
        persist_artifact=False,
    )


def _execute_via_engine(engine: DurableCloudExecutionEngine, worker_id: str) -> dict[str, Any] | None:
    """Execute one job via the engine's queue using a worker."""
    from thinkbox.cloud_execution.worker_config import WorkerConfig
    from thinkbox.cloud_execution.workspace import WorkspaceRegistry

    config = WorkerConfig(worker_id=worker_id, max_active_jobs=1)
    worker = CloudExecutionWorker(engine, config, persist_runtime=False)
    worker.start()
    result = worker.poll_once()
    worker.request_shutdown()
    worker.run_until_idle()
    return {"executed": result, "worker_id": worker_id}


def run_trait_lab_autonomous_worker_cycle(
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
    engine: DurableCloudExecutionEngine,
    gate_mode: str = "gate_regression",
) -> dict[str, Any]:
    """L10 — single claim → gate → execute → receipt loop."""
    require_trait_lab_autonomous_worker_executor_provenance(agent_id=agent_id, task_id=task_id)
    require_trait_lab_autonomous_worker_executor_no_live_ack(environ)

    # Run the Integration Major gate
    integration = _run_integration_gate(
        agent_id=agent_id,
        task_id=task_id,
        environ=environ,
        gate_mode=gate_mode,
    )

    execution_receipt = None
    if integration.get("ok"):
        # Execute via existing engine/worker substrate
        worker_id = f"{agent_id}-worker"
        exec_result = _execute_via_engine(engine, worker_id)
        execution_receipt = exec_result

    return {
        "gate_mode": gate_mode,
        "ok": integration.get("ok", False),
        "integration_report_sha256": integration.get("report", {}).get("integration_report_sha256", ""),
        "execution_receipt": execution_receipt,
        "live_verified": False,
    }


def run_trait_lab_autonomous_worker_continuous(
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
    engine: DurableCloudExecutionEngine,
    gate_mode: str = "gate_regression",
    max_claims: int = 10,
    budget: int = 100,
) -> dict[str, Any]:
    """L11 — run cycles until budget/claims exhausted or shutdown."""
    require_trait_lab_autonomous_worker_executor_provenance(agent_id=agent_id, task_id=task_id)
    require_trait_lab_autonomous_worker_executor_no_live_ack(environ)

    cycle_results: list[dict[str, Any]] = []
    claims = 0
    budget_spent = 0

    while claims < max_claims and budget_spent < budget:
        cycle = run_trait_lab_autonomous_worker_cycle(
            agent_id=agent_id,
            task_id=f"{task_id}:cycle-{claims}",
            environ=environ,
            engine=engine,
            gate_mode=gate_mode,
        )
        cycle_results.append(cycle)
        claims += 1
        if cycle.get("ok"):
            budget_spent += 1
        else:
            # Stop on failure or no work
            if cycle.get("execution_receipt") is None:
                break

    ok = all(r.get("ok", False) for r in cycle_results) if cycle_results else False
    return {
        "gate_mode": gate_mode,
        "cycle_results": cycle_results,
        "claims": claims,
        "budget_spent": budget_spent,
        "budget_remaining": budget - budget_spent,
        "ok": ok,
        "live_verified": False,
    }


def export_trait_lab_autonomous_worker_executor_report(run: Any) -> dict[str, Any]:
    """L12 — signed worker execution report."""
    if not isinstance(run, dict):
        raise MemoryLayerError("invalid_worker", "worker report requires a run")
    refuse_trait_lab_autonomous_worker_executor_live(run)

    cycle_results = run.get("cycle_results")
    if not isinstance(cycle_results, list):
        raise MemoryLayerError("invalid_worker", "cycle_results must be a list")

    ok = all(bool(r.get("ok")) for r in cycle_results if isinstance(r, dict))
    body = {
        "kind": _REPORT_KIND,
        "gate_mode": run.get("gate_mode", "gate_regression"),
        "cycle_results": cycle_results,
        "count": len(cycle_results),
        "claims": run.get("claims", 0),
        "budget_spent": run.get("budget_spent", 0),
        "budget_remaining": run.get("budget_remaining", 0),
        "ok": ok,
        "status": "ready" if ok else "blocked",
        "live_verified": False,
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        **body,
        "worker_report_sha256": hashlib.sha256(encoded).hexdigest(),
        "live_verified": False,
    }


def verify_trait_lab_autonomous_worker_executor_report(report: Any) -> dict[str, Any]:
    """L13 — rematch worker_report_sha256."""
    if not isinstance(report, dict):
        raise MemoryLayerError("invalid_worker", "worker report must be an object")
    if report.get("kind") != _REPORT_KIND:
        raise MemoryLayerError("invalid_worker", "kind must be trait-lab-autonomous-worker-executor-report")
    refuse_trait_lab_autonomous_worker_executor_live(report)
    sha = str(report.get("worker_report_sha256") or "").strip().lower()
    if len(sha) != 64:
        raise MemoryLayerError("missing_worker_report_hash", "verify requires worker_report_sha256")
    mode = _require_gate_mode(report.get("gate_mode"))
    cycle_results = report.get("cycle_results") or []
    ok = bool(report.get("ok"))
    body = {
        "kind": _REPORT_KIND,
        "gate_mode": mode,
        "cycle_results": cycle_results,
        "count": int(report.get("count") or len(cycle_results)),
        "claims": int(report.get("claims") or 0),
        "budget_spent": int(report.get("budget_spent") or 0),
        "budget_remaining": int(report.get("budget_remaining") or 0),
        "ok": ok,
        "status": str(report.get("status") or ""),
        "live_verified": False,
    }
    got = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if got != sha:
        raise MemoryLayerError(
            "worker_report_mismatch",
            f"worker report hashed {got[:12]} not {sha[:12]}",
        )
    return {**body, "matched": True, "worker_report_sha256": sha, "live_verified": False}


def assert_trait_lab_autonomous_worker_executor_ok(run: Any) -> dict[str, Any]:
    """L14 — fail-closed unless all cycles ok."""
    report = verify_trait_lab_autonomous_worker_executor_report(
        export_trait_lab_autonomous_worker_executor_report(run)
    )
    if not report["ok"]:
        raise MemoryLayerError("worker_failed", "autonomous worker executor did not pass")
    return {**report, "asserted": True, "live_verified": False}


def worker_trait_lab_autonomous_executor_status(run: Any) -> str:
    """L15 — ready or blocked."""
    report = export_trait_lab_autonomous_worker_executor_report(run)
    return str(report.get("status") or "blocked")


def trait_lab_autonomous_worker_executor_digest(run: Any) -> str:
    """L16 — worker report SHA-256."""
    return str(export_trait_lab_autonomous_worker_executor_report(run)["worker_report_sha256"])


def trait_lab_autonomous_worker_executor_etag(run: Any) -> str:
    """L17 — short worker identity."""
    return trait_lab_autonomous_worker_executor_digest(run)[:16]


def public_trait_lab_autonomous_worker_executor_row(run: dict[str, Any]) -> dict[str, Any]:
    """L18 — stable summary for dashboards."""
    report = export_trait_lab_autonomous_worker_executor_report(run)
    return {
        "kind": _REPORT_KIND,
        "gate_mode": report["gate_mode"],
        "ok": report["ok"],
        "status": report["status"],
        "worker_report_sha256": report["worker_report_sha256"],
        "live_verified": False,
    }


def manifest_trait_lab_autonomous_worker_executor_config(plan: Any) -> dict[str, Any]:
    """L19 — SDK-friendly config manifest."""
    signed = verify_trait_lab_autonomous_worker_executor(plan)
    return {
        "worker_sha256": signed["worker_sha256"],
        "gate_mode": signed["gate_mode"],
        "queue": signed["queue"],
        "max_claims": signed["max_claims"],
        "budget": signed["budget"],
        "worker_id": signed["worker_id"],
        "live_verified": False,
    }


def bundle_trait_lab_autonomous_worker_executor_for_ci(run: Any) -> dict[str, Any]:
    """L20 — JSON-friendly CI bundle."""
    report = verify_trait_lab_autonomous_worker_executor_report(
        export_trait_lab_autonomous_worker_executor_report(run)
    )
    return {
        "worker": verify_trait_lab_autonomous_worker_executor(run),
        "report": {
            "ok": report["ok"],
            "status": report["status"],
            "worker_report_sha256": report["worker_report_sha256"],
            "cycle_results": [
                {"gate_mode": r.get("gate_mode"), "ok": r.get("ok")}
                for r in report["cycle_results"] if isinstance(r, dict)
            ],
        },
        "live_verified": False,
    }


def compare_trait_lab_autonomous_worker_executor_reports(left: Any, right: Any) -> dict[str, Any]:
    """L21 — compare two worker reports."""
    a = verify_trait_lab_autonomous_worker_executor_report(left)
    b = verify_trait_lab_autonomous_worker_executor_report(right)
    return {
        "same_ok": a["ok"] == b["ok"],
        "same_gate_mode": a["gate_mode"] == b["gate_mode"],
        "same_count": a["count"] == b["count"],
        "live_verified": False,
    }


def trait_lab_autonomous_worker_executor_row(run: Any) -> dict[str, Any]:
    """L22 — one-line worker metadata."""
    return public_trait_lab_autonomous_worker_executor_row(run)


def _fact_id(worker_report_sha256: str) -> str:
    return f"{_FACT_PREFIX}{worker_report_sha256[:16]}"


def persist_trait_lab_autonomous_worker_executor_artifact(
    store: MemoryStore,
    run: Any,
    *,
    agent_id: str,
    task_id: str,
) -> dict[str, Any]:
    """L23 — persist worker report on workspace store."""
    require_trait_lab_autonomous_worker_executor_provenance(agent_id=agent_id, task_id=task_id)
    report = export_trait_lab_autonomous_worker_executor_report(run)
    sha = report["worker_report_sha256"]
    write_verified(
        store,
        _fact_id(sha),
        report,
        layer="task",
        metadata={
            "kind": _REPORT_KIND,
            "worker_report_sha256": sha,
            "ok": report["ok"],
        },
    )
    record_task_step(
        store,
        task_id,
        "autonomous-worker-executor",
        {"worker_report_sha256": sha},
        agent_id=agent_id,
    )
    return {
        "persisted": True,
        "worker_report_sha256": sha,
        "fact_id": _fact_id(sha),
        "live_verified": False,
    }


def trait_lab_autonomous_worker_executor_contract_summary() -> dict[str, Any]:
    """L24 — hermetic catalog for verify scripts."""
    return {
        "gate_id": "memory-trait-lab-autonomous-worker-executor-25",
        "ops_count": len(TRAIT_LAB_AUTONOMOUS_WORKER_EXECUTOR_OPS),
        "gate_modes": list(TRAIT_LAB_AUTONOMOUS_WORKER_GATE_MODES),
        "hermetic_operator_ok": True,
        "live_verified": False,
    }


def open_trait_lab_autonomous_worker_executor(
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
    engine: DurableCloudExecutionEngine,
    gate_mode: str = "gate_regression",
    max_claims: int = 10,
    budget: int = 100,
    persist_artifact: bool = False,
) -> dict[str, Any]:
    """L25 — run worker with queue + Integration Major gate."""
    require_trait_lab_autonomous_worker_executor_provenance(agent_id=agent_id, task_id=task_id)
    require_trait_lab_autonomous_worker_executor_no_live_ack(environ)

    plan = sign_trait_lab_autonomous_worker_executor(plan_trait_lab_autonomous_worker_executor(
        gate_mode=gate_mode,
        max_claims=max_claims,
        budget=budget,
    ))

    run_result = run_trait_lab_autonomous_worker_continuous(
        agent_id=agent_id,
        task_id=task_id,
        environ=environ,
        engine=engine,
        gate_mode=gate_mode,
        max_claims=max_claims,
        budget=budget,
    )

    ok = run_result.get("ok", False)
    result = {
        **plan,
        **run_result,
        "ok": ok,
        "status": "ready" if ok else "blocked",
        "live_verified": False,
    }

    report = export_trait_lab_autonomous_worker_executor_report(result)
    artifact: dict[str, Any] = {"persisted": False}

    if persist_artifact and ok and hasattr(engine, "db_path"):
        store = MemoryStore(engine.db_path)
        try:
            artifact = persist_trait_lab_autonomous_worker_executor_artifact(
                store, result, agent_id=agent_id, task_id=task_id
            )
        finally:
            store.close()

    return {
        **result,
        "report": report,
        "artifact": artifact,
        "worker_open": True,
        "live_verified": False,
    }