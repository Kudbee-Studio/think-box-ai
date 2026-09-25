"""Hermetic Trait Lab autonomous stack harness (U01–U25).

Single entry points for application and integration tests over prep → session →
autonomous → chain bind → flow. No live APIs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from core.memory.store import MemoryStore
from thinkbox.autonomous_flow_workflow import (
    export_trait_lab_autonomous_flow_workflow_artifacts,
    get_trait_lab_autonomous_flow_workflow_receipt,
    has_trait_lab_autonomous_flow_workflow_receipt,
    open_trait_lab_autonomous_flow_workflow,
    plan_trait_lab_autonomous_flow_workflow,
    sign_trait_lab_autonomous_flow_workflow,
)
from thinkbox.autonomous_workflow import (
    require_trait_lab_autonomous_workflow_no_live_ack,
    require_trait_lab_autonomous_workflow_provenance,
)
from thinkbox.autonomous_workflow_chain import (
    has_trait_lab_autonomous_workflow_chain_bind,
    run_trait_lab_autonomous_chained,
    trait_lab_autonomous_workflow_chain_status,
)
from thinkbox.local_env_prep import prepare_trait_lab_local_env_workspace
from thinkbox.memory_layers import MemoryLayerError, record_task_step, write_verified

_SMOKE_KIND = "trait-lab-autonomous-stack-smoke"
_REPORT_KIND = "trait-lab-autonomous-stack-smoke-report"
_SMOKE_FACT_PREFIX = "trait-lab-auto-stack-smoke-"

TRAIT_LAB_AUTONOMOUS_STACK_HARNESS_OPS: tuple[str, ...] = (
    "refuse_live",
    "require_provenance",
    "require_no_live_ack",
    "plan_smoke",
    "validate_smoke_plan",
    "sign_smoke_plan",
    "verify_smoke_plan",
    "run_smoke",
    "smoke_status",
    "export_smoke_report",
    "verify_smoke_report",
    "assert_smoke_ok",
    "list_phases",
    "phase_ok",
    "digest",
    "etag",
    "public_row",
    "rematch_flow_receipt",
    "has_all_receipts",
    "missing_receipts",
    "bundle_for_app",
    "compare_smoke_reports",
    "smoke_row",
    "persist_smoke_artifact",
    "open_smoke_harness",
)

TRAIT_LAB_AUTONOMOUS_STACK_SMOKE_MODES: tuple[str, ...] = ("dry", "run", "full")

TRAIT_LAB_AUTONOMOUS_STACK_PHASES: tuple[str, ...] = (
    "prep",
    "session",
    "autonomous",
    "chain_bind",
    "flow",
)


def refuse_trait_lab_autonomous_stack_harness_live(payload: Any) -> None:
    """U01 — smoke payloads may not claim LIVE VERIFIED."""
    if isinstance(payload, dict) and payload.get("live_verified") is True:
        raise MemoryLayerError("live_claim", "autonomous stack smoke may not claim LIVE VERIFIED")


def require_trait_lab_autonomous_stack_harness_provenance(*, agent_id: str, task_id: str) -> dict[str, Any]:
    """U02 — fail-closed without agent_id and task_id."""
    return require_trait_lab_autonomous_workflow_provenance(agent_id=agent_id, task_id=task_id)


def require_trait_lab_autonomous_stack_harness_no_live_ack(environ: Any = None) -> dict[str, Any]:
    """U03 — fail-closed when swarm live ack is present."""
    return require_trait_lab_autonomous_workflow_no_live_ack(environ)


def _smoke_body(mode: str) -> dict[str, Any]:
    return {
        "kind": _SMOKE_KIND,
        "mode": mode,
        "live_verified": False,
    }


def _require_smoke_mode(mode: Any) -> str:
    wanted = str(mode or "").strip()
    if wanted not in TRAIT_LAB_AUTONOMOUS_STACK_SMOKE_MODES:
        raise MemoryLayerError("invalid_mode", f"unknown smoke mode {wanted or '<empty>'}")
    return wanted


def plan_trait_lab_autonomous_stack_smoke(mode: Any) -> dict[str, Any]:
    """U04 — build an unsigned stack smoke plan."""
    body = _smoke_body(_require_smoke_mode(mode))
    refuse_trait_lab_autonomous_stack_harness_live(body)
    return body


def validate_trait_lab_autonomous_stack_smoke(plan: Any) -> dict[str, Any]:
    """U05 — fail-closed check of a smoke plan."""
    if not isinstance(plan, dict):
        raise MemoryLayerError("invalid_smoke", "stack smoke plan must be an object")
    refuse_trait_lab_autonomous_stack_harness_live(plan)
    if plan.get("kind") not in {None, _SMOKE_KIND}:
        raise MemoryLayerError("invalid_smoke", "kind must be trait-lab-autonomous-stack-smoke")
    mode = _require_smoke_mode(plan.get("mode"))
    return {**_smoke_body(mode), "valid": True}


def sign_trait_lab_autonomous_stack_smoke(plan: Any) -> dict[str, Any]:
    """U06 — sign a validated smoke plan."""
    validated = validate_trait_lab_autonomous_stack_smoke(plan)
    body = _smoke_body(validated["mode"])
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**body, "smoke_sha256": hashlib.sha256(encoded).hexdigest(), "live_verified": False}


def verify_trait_lab_autonomous_stack_smoke(plan: Any) -> dict[str, Any]:
    """U07 — rematch smoke_sha256."""
    if not isinstance(plan, dict):
        raise MemoryLayerError("invalid_smoke", "stack smoke plan must be an object")
    if plan.get("kind") != _SMOKE_KIND:
        raise MemoryLayerError("invalid_smoke", "kind must be trait-lab-autonomous-stack-smoke")
    refuse_trait_lab_autonomous_stack_harness_live(plan)
    mode = _require_smoke_mode(plan.get("mode"))
    sha = str(plan.get("smoke_sha256") or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("missing_smoke_hash", "verify requires smoke_sha256")
    body = _smoke_body(mode)
    got = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if got != sha:
        raise MemoryLayerError("smoke_mismatch", f"smoke hashed {got[:12]} not {sha[:12]}")
    return {**body, "matched": True, "smoke_sha256": sha, "live_verified": False}


def _run_smoke_dry(*, agent_id: str, task_id: str, environ: Any) -> dict[str, Any]:
    workspace = prepare_trait_lab_local_env_workspace()
    store = MemoryStore(workspace["store_path"])
    try:
        from thinkbox.autonomous_flow_workflow import dry_run_trait_lab_autonomous_flow_workflow

        flow_plan = sign_trait_lab_autonomous_flow_workflow(
            plan_trait_lab_autonomous_flow_workflow(["dry_run"])
        )
        ran = dry_run_trait_lab_autonomous_flow_workflow(
            store, flow_plan, agent_id=agent_id, task_id=task_id, environ=environ
        )
    finally:
        store.close()
    return {
        **ran,
        "mode": "dry",
        "workspace": workspace,
        "wrote": False,
        "live_verified": False,
    }


def _run_smoke_run(*, agent_id: str, task_id: str, environ: Any) -> dict[str, Any]:
    chained = run_trait_lab_autonomous_chained(agent_id=agent_id, task_id=task_id, environ=environ)
    return {
        **chained,
        "mode": "run",
        "live_verified": False,
    }


def _run_smoke_full(*, agent_id: str, task_id: str, environ: Any) -> dict[str, Any]:
    opened = open_trait_lab_autonomous_flow_workflow(
        agent_id=agent_id, task_id=task_id, environ=environ
    )
    return {
        **opened,
        "mode": "full",
        "live_verified": False,
    }


def run_trait_lab_autonomous_stack_smoke(
    plan: Any,
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
) -> dict[str, Any]:
    """U08 — execute stack smoke for dry, run, or full mode."""
    require_trait_lab_autonomous_stack_harness_provenance(agent_id=agent_id, task_id=task_id)
    require_trait_lab_autonomous_stack_harness_no_live_ack(environ)
    signed = sign_trait_lab_autonomous_stack_smoke(plan)
    mode = signed["mode"]
    if mode == "dry":
        result = _run_smoke_dry(agent_id=agent_id, task_id=task_id, environ=environ)
    elif mode == "run":
        result = _run_smoke_run(agent_id=agent_id, task_id=task_id, environ=environ)
    else:
        result = _run_smoke_full(agent_id=agent_id, task_id=task_id, environ=environ)
    status = smoke_trait_lab_autonomous_stack_status(result)
    ok = bool(result.get("ok", True)) and status in {"dry_run", "ready"}
    return {
        **signed,
        "result": result,
        "status": status,
        "ok": ok,
        "live_verified": False,
    }


def smoke_trait_lab_autonomous_stack_status(result: Any) -> str:
    """U09 — dry_run, ready, blocked, or planned."""
    if not isinstance(result, dict):
        raise MemoryLayerError("invalid_smoke", "smoke status requires a result")
    refuse_trait_lab_autonomous_stack_harness_live(result)
    mode = str(result.get("mode") or "")
    if mode == "dry" or result.get("wrote") is False:
        return "dry_run"
    if result.get("flow_persisted") is True or result.get("opened") is True:
        return "ready"
    if result.get("chained") is True:
        return trait_lab_autonomous_workflow_chain_status(result)
    if result.get("ok") is False:
        return "blocked"
    if result.get("smoke_sha256"):
        return "planned"
    raise MemoryLayerError("invalid_smoke", "smoke status is missing")


def _phase_row(*, name: str, ok: bool, sha256: str = "") -> dict[str, Any]:
    return {
        "phase": name,
        "ok": ok,
        "sha256": sha256,
        "live_verified": False,
    }


def export_trait_lab_autonomous_stack_smoke_report(run: Any) -> dict[str, Any]:
    """U10 — normalize smoke run into phase rows for app assertions."""
    if not isinstance(run, dict):
        raise MemoryLayerError("invalid_smoke", "smoke report requires a run object")
    refuse_trait_lab_autonomous_stack_harness_live(run)
    result = run.get("result") if "result" in run else run
    if not isinstance(result, dict):
        raise MemoryLayerError("invalid_smoke", "smoke run missing result")
    mode = str(result.get("mode") or run.get("mode") or "")
    if mode not in TRAIT_LAB_AUTONOMOUS_STACK_SMOKE_MODES:
        mode = str(verify_trait_lab_autonomous_stack_smoke(run).get("mode") or "run")
    phases: dict[str, dict[str, Any]] = {}
    store_path = ""

    if mode == "dry":
        inner = result.get("results")
        if isinstance(inner, list) and inner:
            dry = inner[0]
            chain_index = dry.get("chain_index") if isinstance(dry, dict) else {}
            phases["chain_bind"] = _phase_row(
                name="chain_bind",
                ok=True,
                sha256=str((chain_index or {}).get("chain_index_sha256") or ""),
            )
        phases["prep"] = _phase_row(name="prep", ok=True)
        phases["session"] = _phase_row(name="session", ok=True)
        phases["autonomous"] = _phase_row(name="autonomous", ok=True)
        phases["flow"] = _phase_row(name="flow", ok=bool(result.get("ok", True)))
        workspace = result.get("workspace") if isinstance(result.get("workspace"), dict) else {}
        store_path = str(workspace.get("store_path") or "")
    elif mode == "run":
        run_body = result.get("run") if isinstance(result.get("run"), dict) else {}
        auto = run_body.get("autonomous") if isinstance(run_body.get("autonomous"), dict) else {}
        phases["prep"] = _phase_row(
            name="prep",
            ok=True,
            sha256=str(auto.get("prep_sha256") or run_body.get("prep_sha256") or ""),
        )
        phases["session"] = _phase_row(
            name="session",
            ok=True,
            sha256=str(auto.get("session_sha256") or run_body.get("session_sha256") or ""),
        )
        phases["autonomous"] = _phase_row(
            name="autonomous",
            ok=True,
            sha256=str(auto.get("autonomous_sha256") or ""),
        )
        bind = result.get("bind") if isinstance(result.get("bind"), dict) else {}
        phases["chain_bind"] = _phase_row(
            name="chain_bind",
            ok=bool(result.get("ok")),
            sha256=str(bind.get("bind_sha256") or ""),
        )
        phases["flow"] = _phase_row(name="flow", ok=False)
        workspace = run_body.get("workspace") if isinstance(run_body.get("workspace"), dict) else {}
        store_path = str(workspace.get("store_path") or "")
    else:
        artifacts = export_trait_lab_autonomous_flow_workflow_artifacts(result)
        phases["prep"] = _phase_row(name="prep", ok=True, sha256=str(artifacts.get("prep_sha256") or ""))
        phases["session"] = _phase_row(
            name="session", ok=True, sha256=str(artifacts.get("session_sha256") or "")
        )
        phases["autonomous"] = _phase_row(
            name="autonomous", ok=True, sha256=str(artifacts.get("autonomous_sha256") or "")
        )
        phases["chain_bind"] = _phase_row(
            name="chain_bind", ok=True, sha256=str(artifacts.get("bind_sha256") or "")
        )
        phases["flow"] = _phase_row(
            name="flow",
            ok=bool(result.get("flow_persisted")),
            sha256=str(result.get("flow_sha256") or ""),
        )
        inner = result.get("results")
        if isinstance(inner, list) and inner:
            last = inner[-1]
            run_body = last.get("run") if isinstance(last, dict) and isinstance(last.get("run"), dict) else {}
            workspace = run_body.get("workspace") if isinstance(run_body.get("workspace"), dict) else {}
            store_path = str(workspace.get("store_path") or "")

    phase_list = [phases[name] for name in TRAIT_LAB_AUTONOMOUS_STACK_PHASES if name in phases]
    body = {
        "kind": _REPORT_KIND,
        "mode": mode,
        "phases": phase_list,
        "store_path": store_path,
        "status": smoke_trait_lab_autonomous_stack_status(result),
        "ok": bool(run.get("ok", result.get("ok", True))),
        "live_verified": False,
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**body, "report_sha256": hashlib.sha256(encoded).hexdigest(), "live_verified": False}


def verify_trait_lab_autonomous_stack_smoke_report(report: Any) -> dict[str, Any]:
    """U11 — rematch report_sha256."""
    if not isinstance(report, dict):
        raise MemoryLayerError("invalid_smoke", "smoke report must be an object")
    if report.get("kind") != _REPORT_KIND:
        raise MemoryLayerError("invalid_smoke", "kind must be trait-lab-autonomous-stack-smoke-report")
    refuse_trait_lab_autonomous_stack_harness_live(report)
    mode = _require_smoke_mode(report.get("mode"))
    if not isinstance(report.get("phases"), list):
        raise MemoryLayerError("invalid_smoke", "phases must be a list")
    sha = str(report.get("report_sha256") or "").strip().lower()
    if len(sha) != 64:
        raise MemoryLayerError("missing_report_hash", "verify requires report_sha256")
    body = {
        "kind": _REPORT_KIND,
        "mode": mode,
        "phases": report["phases"],
        "store_path": str(report.get("store_path") or ""),
        "status": str(report.get("status") or ""),
        "ok": bool(report.get("ok", True)),
        "live_verified": False,
    }
    got = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if got != sha:
        raise MemoryLayerError("report_mismatch", f"report hashed {got[:12]} not {sha[:12]}")
    return {**body, "matched": True, "report_sha256": sha, "live_verified": False}


def assert_trait_lab_autonomous_stack_smoke_ok(run: Any) -> dict[str, Any]:
    """U12 — fail-closed when smoke run is not ok."""
    report = export_trait_lab_autonomous_stack_smoke_report(run)
    if not report["ok"]:
        raise MemoryLayerError("smoke_failed", "stack smoke run is not ok")
    missing = missing_trait_lab_autonomous_stack_receipts(run)
    if missing["count"] > 0 and report["mode"] == "full":
        raise MemoryLayerError("smoke_failed", f"missing receipts: {missing['missing']}")
    return {**report, "asserted": True, "live_verified": False}


def list_trait_lab_autonomous_stack_phases(run: Any) -> list[str]:
    """U13 — phase names present in the smoke report."""
    report = export_trait_lab_autonomous_stack_smoke_report(run)
    return [str(row.get("phase") or "") for row in report["phases"]]


def trait_lab_autonomous_stack_phase_ok(run: Any, phase: str) -> bool:
    """U14 — true when the named phase row is ok."""
    wanted = str(phase or "").strip()
    if wanted not in TRAIT_LAB_AUTONOMOUS_STACK_PHASES:
        raise MemoryLayerError("invalid_phase", f"unknown phase {wanted or '<empty>'}")
    report = export_trait_lab_autonomous_stack_smoke_report(run)
    for row in report["phases"]:
        if row.get("phase") == wanted:
            return bool(row.get("ok"))
    return False


def trait_lab_autonomous_stack_smoke_digest(run: Any) -> str:
    """U15 — report SHA-256."""
    return str(export_trait_lab_autonomous_stack_smoke_report(run)["report_sha256"])


def trait_lab_autonomous_stack_smoke_etag(run: Any) -> str:
    """U16 — short report identity."""
    return trait_lab_autonomous_stack_smoke_digest(run)[:16]


def public_trait_lab_autonomous_stack_smoke_row(run: dict[str, Any]) -> dict[str, Any]:
    """U17 — stable summary for dashboards."""
    report = export_trait_lab_autonomous_stack_smoke_report(run)
    return {
        "kind": _REPORT_KIND,
        "mode": report["mode"],
        "status": report["status"],
        "ok": report["ok"],
        "report_sha256": report["report_sha256"],
        "live_verified": False,
    }


def rematch_trait_lab_autonomous_stack_flow_receipt(store: MemoryStore, run: Any) -> dict[str, Any]:
    """U18 — verify persisted flow receipt matches the smoke run."""
    report = export_trait_lab_autonomous_stack_smoke_report(run)
    if report["mode"] != "full":
        raise MemoryLayerError("invalid_smoke", "flow rematch requires full mode")
    flow_row = next((p for p in report["phases"] if p.get("phase") == "flow"), None)
    if flow_row is None:
        raise MemoryLayerError("missing_flow", "smoke report has no flow phase")
    sha = str(flow_row.get("sha256") or "").strip().lower()
    if len(sha) != 64:
        raise MemoryLayerError("missing_flow_hash", "flow phase missing flow_sha256")
    receipt = get_trait_lab_autonomous_flow_workflow_receipt(store, sha)
    if receipt["flow_sha256"] != sha:
        raise MemoryLayerError("flow_mismatch", "store flow receipt disagrees with smoke")
    return {**receipt, "rematched": True, "live_verified": False}


def has_trait_lab_autonomous_stack_all_receipts(store: MemoryStore, run: Any) -> bool:
    """U19 — true when full-mode smoke receipts exist in store."""
    return missing_trait_lab_autonomous_stack_receipts(run, store=store)["count"] == 0


def missing_trait_lab_autonomous_stack_receipts(
    run: Any,
    *,
    store: MemoryStore | None = None,
) -> dict[str, Any]:
    """U20 — receipt phases not found in store (full mode only)."""
    report = export_trait_lab_autonomous_stack_smoke_report(run)
    missing: list[str] = []
    if report["mode"] != "full":
        return {"missing": missing, "count": 0, "live_verified": False}
    if store is None:
        path = str(report.get("store_path") or "").strip()
        if not path:
            return {"missing": list(TRAIT_LAB_AUTONOMOUS_STACK_PHASES), "count": 5, "live_verified": False}
        store = MemoryStore(path)
        close = True
    else:
        close = False
    try:
        flow_row = next((p for p in report["phases"] if p.get("phase") == "flow"), None)
        if flow_row and flow_row.get("ok"):
            sha = str(flow_row.get("sha256") or "")
            if not has_trait_lab_autonomous_flow_workflow_receipt(store, sha):
                missing.append("flow")
        bind_row = next((p for p in report["phases"] if p.get("phase") == "chain_bind"), None)
        if bind_row and bind_row.get("ok"):
            bind_sha = str(bind_row.get("sha256") or "")
            if bind_sha and not has_trait_lab_autonomous_workflow_chain_bind(store, bind_sha):
                missing.append("chain_bind")
    finally:
        if close:
            store.close()
    return {"missing": missing, "count": len(missing), "live_verified": False}


def bundle_trait_lab_autonomous_stack_for_app(run: Any) -> dict[str, Any]:
    """U21 — JSON-friendly bundle for application test fixtures."""
    report = verify_trait_lab_autonomous_stack_smoke_report(export_trait_lab_autonomous_stack_smoke_report(run))
    return {
        "smoke": verify_trait_lab_autonomous_stack_smoke(run) if run.get("smoke_sha256") else {},
        "report": {
            "mode": report["mode"],
            "status": report["status"],
            "ok": report["ok"],
            "report_sha256": report["report_sha256"],
            "phases": report["phases"],
        },
        "live_verified": False,
    }


def compare_trait_lab_autonomous_stack_smoke_reports(left: Any, right: Any) -> dict[str, Any]:
    """U22 — compare two signed smoke reports (mode and ok only)."""
    a = verify_trait_lab_autonomous_stack_smoke_report(left)
    b = verify_trait_lab_autonomous_stack_smoke_report(right)
    return {
        "same_mode": a["mode"] == b["mode"],
        "same_ok": a["ok"] == b["ok"],
        "same_status": a["status"] == b["status"],
        "live_verified": False,
    }


def trait_lab_autonomous_stack_smoke_row(run: Any) -> dict[str, Any]:
    """U23 — one-line smoke metadata."""
    return public_trait_lab_autonomous_stack_smoke_row(run)


def _smoke_fact_id(report_sha256: str) -> str:
    return f"{_SMOKE_FACT_PREFIX}{report_sha256[:16]}"


def persist_trait_lab_autonomous_stack_smoke_artifact(
    store: MemoryStore,
    run: Any,
    *,
    agent_id: str,
    task_id: str,
) -> dict[str, Any]:
    """U24 — persist smoke report snapshot for audit."""
    require_trait_lab_autonomous_stack_harness_provenance(agent_id=agent_id, task_id=task_id)
    report = verify_trait_lab_autonomous_stack_smoke_report(export_trait_lab_autonomous_stack_smoke_report(run))
    sha = str(report["report_sha256"])
    write_verified(
        store,
        {
            "id": _smoke_fact_id(sha),
            "fact": f"autonomous stack smoke {sha} mode={report['mode']}",
            "how": f"persist_trait_lab_autonomous_stack_smoke_artifact {sha}",
            "confidence": 1.0,
            "source": sha,
            "agent_id": agent_id,
            "task_id": task_id,
            "kind": _REPORT_KIND,
            "mode": report["mode"],
            "ok": report["ok"],
            "report_sha256": sha,
        },
    )
    record_task_step(
        store,
        task_id,
        "autonomous-stack-smoke",
        {"report_sha256": sha, "mode": report["mode"]},
        agent_id=agent_id,
    )
    return {
        "persisted": True,
        "report_sha256": sha,
        "fact_id": _smoke_fact_id(sha),
        "live_verified": False,
    }


def open_trait_lab_autonomous_stack_harness(
    *,
    mode: str = "full",
    agent_id: str,
    task_id: str,
    environ: Any = None,
    persist_artifact: bool = False,
) -> dict[str, Any]:
    """U25 — plan, run, report, and optionally persist smoke artifact (app test entry)."""
    plan = sign_trait_lab_autonomous_stack_smoke(plan_trait_lab_autonomous_stack_smoke(mode))
    ran = run_trait_lab_autonomous_stack_smoke(
        plan, agent_id=agent_id, task_id=task_id, environ=environ
    )
    report = export_trait_lab_autonomous_stack_smoke_report(ran)
    artifact: dict[str, Any] = {"persisted": False}
    if persist_artifact and report["mode"] == "full":
        path = str(report.get("store_path") or "").strip()
        if path:
            store = MemoryStore(path)
            try:
                artifact = persist_trait_lab_autonomous_stack_smoke_artifact(
                    store, ran, agent_id=agent_id, task_id=task_id
                )
            finally:
                store.close()
    return {
        **ran,
        "report": report,
        "artifact": artifact,
        "harness_open": True,
        "live_verified": False,
    }
