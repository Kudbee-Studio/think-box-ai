"""Hermetic Trait Lab autonomous app gate (G01–G25).

Fail-closed gate for application/CI: run stack suite and emit a signed pass report.
No live APIs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from core.memory.store import MemoryStore
from thinkbox.autonomous_stack_harness import require_trait_lab_autonomous_stack_harness_no_live_ack
from thinkbox.autonomous_stack_suite import (
    assert_trait_lab_autonomous_stack_suite_ok,
    bundle_trait_lab_autonomous_stack_for_ci,
    export_trait_lab_autonomous_stack_suite_report,
    open_trait_lab_autonomous_stack_suite,
    require_trait_lab_autonomous_stack_suite_provenance,
)
from thinkbox.autonomous_workflow import require_trait_lab_autonomous_workflow_provenance
from thinkbox.memory_layers import MemoryLayerError, record_task_step, write_verified

_GATE_KIND = "trait-lab-autonomous-app-gate"
_REPORT_KIND = "trait-lab-autonomous-app-gate-report"
_GATE_FACT_PREFIX = "trait-lab-auto-app-gate-"

TRAIT_LAB_AUTONOMOUS_APP_GATE_OPS: tuple[str, ...] = (
    "refuse_live",
    "require_provenance",
    "require_no_live_ack",
    "plan_gate",
    "validate_gate",
    "sign_gate",
    "verify_gate",
    "run_gate",
    "gate_status",
    "export_gate_report",
    "verify_gate_report",
    "assert_gate_pass",
    "list_checks",
    "check_ok",
    "digest",
    "etag",
    "public_row",
    "rematch_suite_report",
    "has_gate_pass",
    "bundle_for_ci",
    "compare_gate_reports",
    "gate_row",
    "persist_gate_artifact",
    "contract_summary",
    "open_app_gate",
)

TRAIT_LAB_AUTONOMOUS_APP_GATE_CHECKS: tuple[str, ...] = ("stack_suite",)


def refuse_trait_lab_autonomous_app_gate_live(payload: Any) -> None:
    """G01 — gate payloads may not claim LIVE VERIFIED."""
    if isinstance(payload, dict) and payload.get("live_verified") is True:
        raise MemoryLayerError("live_claim", "autonomous app gate may not claim LIVE VERIFIED")


def require_trait_lab_autonomous_app_gate_provenance(*, agent_id: str, task_id: str) -> dict[str, Any]:
    """G02 — fail-closed without agent_id and task_id."""
    return require_trait_lab_autonomous_workflow_provenance(agent_id=agent_id, task_id=task_id)


def require_trait_lab_autonomous_app_gate_no_live_ack(environ: Any = None) -> dict[str, Any]:
    """G03 — fail-closed when swarm live ack is present."""
    return require_trait_lab_autonomous_stack_harness_no_live_ack(environ)


def _gate_body(checks: list[str]) -> dict[str, Any]:
    return {
        "kind": _GATE_KIND,
        "checks": checks,
        "count": len(checks),
        "live_verified": False,
    }


def _require_gate_checks(checks: Any) -> list[str]:
    if not isinstance(checks, list) or not checks:
        raise MemoryLayerError("missing_check", "app gate requires at least one check")
    allowed = set(TRAIT_LAB_AUTONOMOUS_APP_GATE_CHECKS)
    names: list[str] = []
    for item in checks:
        name = str(item or "").strip()
        if name not in allowed:
            raise MemoryLayerError("invalid_check", f"unknown gate check {name or '<empty>'}")
        names.append(name)
    return names


def plan_trait_lab_autonomous_app_gate(checks: Any = None) -> dict[str, Any]:
    """G04 — unsigned gate plan (default: stack_suite)."""
    selected = _require_gate_checks(list(checks) if checks is not None else ["stack_suite"])
    body = _gate_body(selected)
    refuse_trait_lab_autonomous_app_gate_live(body)
    return body


def validate_trait_lab_autonomous_app_gate(plan: Any) -> dict[str, Any]:
    """G05 — fail-closed validation."""
    if not isinstance(plan, dict):
        raise MemoryLayerError("invalid_gate", "app gate plan must be an object")
    refuse_trait_lab_autonomous_app_gate_live(plan)
    if plan.get("kind") not in {None, _GATE_KIND}:
        raise MemoryLayerError("invalid_gate", "kind must be trait-lab-autonomous-app-gate")
    checks = _require_gate_checks(plan.get("checks"))
    return {**_gate_body(checks), "valid": True}


def sign_trait_lab_autonomous_app_gate(plan: Any) -> dict[str, Any]:
    """G06 — sign gate plan."""
    validated = validate_trait_lab_autonomous_app_gate(plan)
    body = _gate_body(validated["checks"])
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**body, "gate_sha256": hashlib.sha256(encoded).hexdigest(), "live_verified": False}


def verify_trait_lab_autonomous_app_gate(plan: Any) -> dict[str, Any]:
    """G07 — rematch gate_sha256."""
    if not isinstance(plan, dict):
        raise MemoryLayerError("invalid_gate", "app gate plan must be an object")
    if plan.get("kind") != _GATE_KIND:
        raise MemoryLayerError("invalid_gate", "kind must be trait-lab-autonomous-app-gate")
    refuse_trait_lab_autonomous_app_gate_live(plan)
    checks = _require_gate_checks(plan.get("checks"))
    sha = str(plan.get("gate_sha256") or "").strip().lower()
    if len(sha) != 64:
        raise MemoryLayerError("missing_gate_hash", "verify requires gate_sha256")
    body = _gate_body(checks)
    got = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if got != sha:
        raise MemoryLayerError("gate_mismatch", f"gate hashed {got[:12]} not {sha[:12]}")
    return {**body, "matched": True, "gate_sha256": sha, "live_verified": False}


def run_trait_lab_autonomous_app_gate(
    plan: Any,
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
) -> dict[str, Any]:
    """G08 — execute gate checks (stack suite when listed)."""
    require_trait_lab_autonomous_app_gate_provenance(agent_id=agent_id, task_id=task_id)
    require_trait_lab_autonomous_app_gate_no_live_ack(environ)
    signed = sign_trait_lab_autonomous_app_gate(plan)
    results: list[dict[str, Any]] = []
    suite: dict[str, Any] | None = None
    for check in signed["checks"]:
        if check == "stack_suite":
            require_trait_lab_autonomous_stack_suite_provenance(agent_id=agent_id, task_id=task_id)
            suite = open_trait_lab_autonomous_stack_suite(
                agent_id=agent_id,
                task_id=f"{task_id}:gate",
                environ=environ,
                persist_artifact=True,
            )
            ok = bool(suite.get("ok"))
            results.append(
                {
                    "check": check,
                    "ok": ok,
                    "suite_report_sha256": str(
                        (suite.get("report") or {}).get("suite_report_sha256") or ""
                    ),
                    "live_verified": False,
                }
            )
        else:
            raise MemoryLayerError("invalid_check", f"unimplemented gate check {check}")
    passed = all(r["ok"] for r in results)
    return {
        **signed,
        "results": results,
        "passed": passed,
        "ok": passed,
        "status": "ready" if passed else "blocked",
        "suite": suite,
        "live_verified": False,
    }


def gate_trait_lab_autonomous_app_status(run: Any) -> str:
    """G09 — ready or blocked."""
    if not isinstance(run, dict):
        raise MemoryLayerError("invalid_gate", "gate status requires a run")
    refuse_trait_lab_autonomous_app_gate_live(run)
    if run.get("passed") is True or run.get("ok") is True:
        return "ready"
    if run.get("ok") is False or run.get("passed") is False:
        return "blocked"
    raise MemoryLayerError("invalid_gate", "gate status is missing")


def export_trait_lab_autonomous_app_gate_report(run: Any) -> dict[str, Any]:
    """G10 — signed gate pass/fail report."""
    if not isinstance(run, dict):
        raise MemoryLayerError("invalid_gate", "gate report requires a run")
    refuse_trait_lab_autonomous_app_gate_live(run)
    gate = verify_trait_lab_autonomous_app_gate(run)
    results = run.get("results")
    if not isinstance(results, list):
        raise MemoryLayerError("invalid_gate", "results must be a list")
    body = {
        "kind": _REPORT_KIND,
        "checks": gate["checks"],
        "results": results,
        "count": len(results),
        "passed": bool(run.get("passed", run.get("ok"))),
        "status": gate_trait_lab_autonomous_app_status(run),
        "gate_sha256": gate["gate_sha256"],
        "live_verified": False,
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**body, "gate_report_sha256": hashlib.sha256(encoded).hexdigest(), "live_verified": False}


def verify_trait_lab_autonomous_app_gate_report(report: Any) -> dict[str, Any]:
    """G11 — rematch gate_report_sha256."""
    if not isinstance(report, dict):
        raise MemoryLayerError("invalid_gate", "gate report must be an object")
    if report.get("kind") != _REPORT_KIND:
        raise MemoryLayerError("invalid_gate", "kind must be trait-lab-autonomous-app-gate-report")
    refuse_trait_lab_autonomous_app_gate_live(report)
    sha = str(report.get("gate_report_sha256") or "").strip().lower()
    if len(sha) != 64:
        raise MemoryLayerError("missing_gate_report_hash", "verify requires gate_report_sha256")
    body = {
        "kind": _REPORT_KIND,
        "checks": _require_gate_checks(report.get("checks")),
        "results": report.get("results") or [],
        "count": int(report.get("count") or 0),
        "passed": bool(report.get("passed")),
        "status": str(report.get("status") or ""),
        "gate_sha256": str(report.get("gate_sha256") or "").lower(),
        "live_verified": False,
    }
    got = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if got != sha:
        raise MemoryLayerError("gate_report_mismatch", f"gate report hashed {got[:12]} not {sha[:12]}")
    return {**body, "matched": True, "gate_report_sha256": sha, "live_verified": False}


def assert_trait_lab_autonomous_app_gate_pass(run: Any) -> dict[str, Any]:
    """G12 — fail-closed unless gate passed."""
    report = verify_trait_lab_autonomous_app_gate_report(export_trait_lab_autonomous_app_gate_report(run))
    if not report["passed"]:
        raise MemoryLayerError("gate_failed", "autonomous app gate did not pass")
    suite = run.get("suite")
    if isinstance(suite, dict):
        assert_trait_lab_autonomous_stack_suite_ok(suite)
    return {**report, "asserted": True, "live_verified": False}


def list_trait_lab_autonomous_app_gate_checks(plan: Any) -> list[str]:
    """G13 — check names from a gate plan."""
    return list(verify_trait_lab_autonomous_app_gate(plan)["checks"])


def trait_lab_autonomous_app_gate_check_ok(run: Any, check: str) -> bool:
    """G14 — true when named check passed."""
    wanted = str(check or "").strip()
    for row in run.get("results") or []:
        if isinstance(row, dict) and row.get("check") == wanted:
            return bool(row.get("ok"))
    return False


def trait_lab_autonomous_app_gate_digest(run: Any) -> str:
    """G15 — gate report SHA-256."""
    return str(export_trait_lab_autonomous_app_gate_report(run)["gate_report_sha256"])


def trait_lab_autonomous_app_gate_etag(run: Any) -> str:
    """G16 — short gate identity."""
    return trait_lab_autonomous_app_gate_digest(run)[:16]


def public_trait_lab_autonomous_app_gate_row(run: dict[str, Any]) -> dict[str, Any]:
    """G17 — stable gate summary."""
    report = export_trait_lab_autonomous_app_gate_report(run)
    return {
        "kind": _REPORT_KIND,
        "passed": report["passed"],
        "status": report["status"],
        "gate_report_sha256": report["gate_report_sha256"],
        "live_verified": False,
    }


def rematch_trait_lab_autonomous_app_gate_suite_report(run: Any) -> dict[str, Any]:
    """G18 — verify suite report embedded in gate run."""
    suite = run.get("suite")
    if not isinstance(suite, dict):
        raise MemoryLayerError("missing_suite", "gate run has no suite")
    report = export_trait_lab_autonomous_stack_suite_report(suite)
    for row in run.get("results") or []:
        if isinstance(row, dict) and row.get("check") == "stack_suite":
            expected = str(row.get("suite_report_sha256") or "")
            if expected and report.get("suite_report_sha256") != expected:
                raise MemoryLayerError("suite_mismatch", "gate suite report disagrees with run")
    return {**report, "rematched": True, "live_verified": False}


def trait_lab_autonomous_app_gate_has_pass(run: Any) -> bool:
    """G19 — true when gate report says passed."""
    return bool(export_trait_lab_autonomous_app_gate_report(run).get("passed"))


def bundle_trait_lab_autonomous_app_gate_for_ci(run: Any) -> dict[str, Any]:
    """G20 — CI-friendly gate + suite bundle."""
    gate_report = verify_trait_lab_autonomous_app_gate_report(export_trait_lab_autonomous_app_gate_report(run))
    suite_bundle: dict[str, Any] = {}
    suite = run.get("suite")
    if isinstance(suite, dict):
        suite_bundle = bundle_trait_lab_autonomous_stack_for_ci(suite)
    return {
        "gate": {
            "passed": gate_report["passed"],
            "status": gate_report["status"],
            "gate_report_sha256": gate_report["gate_report_sha256"],
        },
        "suite": suite_bundle,
        "live_verified": False,
    }


def compare_trait_lab_autonomous_app_gate_reports(left: Any, right: Any) -> dict[str, Any]:
    """G21 — compare two gate reports."""
    a = verify_trait_lab_autonomous_app_gate_report(left)
    b = verify_trait_lab_autonomous_app_gate_report(right)
    return {
        "same_passed": a["passed"] == b["passed"],
        "same_status": a["status"] == b["status"],
        "live_verified": False,
    }


def trait_lab_autonomous_app_gate_row(run: Any) -> dict[str, Any]:
    """G22 — one-line gate metadata."""
    return public_trait_lab_autonomous_app_gate_row(run)


def _gate_fact_id(gate_report_sha256: str) -> str:
    return f"{_GATE_FACT_PREFIX}{gate_report_sha256[:16]}"


def persist_trait_lab_autonomous_app_gate_artifact(
    store: MemoryStore,
    run: Any,
    *,
    agent_id: str,
    task_id: str,
) -> dict[str, Any]:
    """G23 — persist gate report on workspace store."""
    require_trait_lab_autonomous_app_gate_provenance(agent_id=agent_id, task_id=task_id)
    report = verify_trait_lab_autonomous_app_gate_report(export_trait_lab_autonomous_app_gate_report(run))
    sha = str(report["gate_report_sha256"])
    write_verified(
        store,
        {
            "id": _gate_fact_id(sha),
            "fact": f"autonomous app gate {sha} passed={report['passed']}",
            "how": f"persist_trait_lab_autonomous_app_gate_artifact {sha}",
            "confidence": 1.0,
            "source": sha,
            "agent_id": agent_id,
            "task_id": task_id,
            "kind": _REPORT_KIND,
            "passed": report["passed"],
            "gate_report_sha256": sha,
        },
    )
    record_task_step(
        store,
        task_id,
        "autonomous-app-gate",
        {"gate_report_sha256": sha, "passed": report["passed"]},
        agent_id=agent_id,
    )
    return {
        "persisted": True,
        "gate_report_sha256": sha,
        "fact_id": _gate_fact_id(sha),
        "live_verified": False,
    }


def trait_lab_autonomous_app_gate_contract_summary() -> dict[str, Any]:
    """G24 — hermetic gate catalog for verify scripts."""
    return {
        "gate_id": "memory-trait-lab-autonomous-app-gate-25",
        "ops_count": len(TRAIT_LAB_AUTONOMOUS_APP_GATE_OPS),
        "checks": list(TRAIT_LAB_AUTONOMOUS_APP_GATE_CHECKS),
        "hermetic_operator_ok": True,
        "live_verified": False,
    }


def open_trait_lab_autonomous_app_gate(
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
    persist_artifact: bool = True,
) -> dict[str, Any]:
    """G25 — default stack_suite gate for application CI."""
    plan = sign_trait_lab_autonomous_app_gate(plan_trait_lab_autonomous_app_gate())
    ran = run_trait_lab_autonomous_app_gate(plan, agent_id=agent_id, task_id=task_id, environ=environ)
    report = export_trait_lab_autonomous_app_gate_report(ran)
    artifact: dict[str, Any] = {"persisted": False}
    if persist_artifact and isinstance(ran.get("suite"), dict):
        from thinkbox.autonomous_stack_harness import export_trait_lab_autonomous_stack_smoke_report

        for srow in ran["suite"].get("runs") or []:
            if not isinstance(srow, dict) or srow.get("mode") != "full" or not srow.get("ok"):
                continue
            full_run = srow.get("run")
            if not isinstance(full_run, dict):
                continue
            smoke = export_trait_lab_autonomous_stack_smoke_report(full_run)
            path = str(smoke.get("store_path") or "").strip()
            if not path:
                continue
            store = MemoryStore(path)
            try:
                artifact = persist_trait_lab_autonomous_app_gate_artifact(
                    store, ran, agent_id=agent_id, task_id=task_id
                )
            finally:
                store.close()
            break
    return {
        **ran,
        "report": report,
        "gate_artifact": artifact,
        "gate_open": True,
        "live_verified": False,
    }
