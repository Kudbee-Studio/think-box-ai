"""Hermetic Trait Lab autonomous app regression (J01–J25).

Compare a signed baseline gate report to a fresh gate run for CI drift checks.
No live APIs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from core.memory.store import MemoryStore
from thinkbox.autonomous_app_gate import (
    compare_trait_lab_autonomous_app_gate_reports,
    export_trait_lab_autonomous_app_gate_report,
    open_trait_lab_autonomous_app_gate,
    require_trait_lab_autonomous_app_gate_no_live_ack,
    require_trait_lab_autonomous_app_gate_provenance,
    verify_trait_lab_autonomous_app_gate_report,
)
from thinkbox.memory_layers import MemoryLayerError, record_task_step, write_verified

_REGRESSION_KIND = "trait-lab-autonomous-app-regression"
_REPORT_KIND = "trait-lab-autonomous-app-regression-report"
_FACT_PREFIX = "trait-lab-auto-app-regression-"

TRAIT_LAB_AUTONOMOUS_APP_REGRESSION_OPS: tuple[str, ...] = (
    "refuse_live",
    "require_provenance",
    "require_no_live_ack",
    "plan_regression",
    "validate_regression",
    "sign_regression",
    "verify_regression",
    "capture_baseline",
    "capture_candidate",
    "compare_reports",
    "export_regression_report",
    "verify_regression_report",
    "assert_no_regression",
    "regression_status",
    "digest",
    "etag",
    "public_row",
    "rematch_baseline",
    "rematch_candidate",
    "bundle_for_ci",
    "compare_regression_reports",
    "regression_row",
    "persist_regression_artifact",
    "contract_summary",
    "open_app_regression",
)

TRAIT_LAB_AUTONOMOUS_APP_REGRESSION_MODES: tuple[str, ...] = ("capture", "compare")


def refuse_trait_lab_autonomous_app_regression_live(payload: Any) -> None:
    """J01 — regression payloads may not claim LIVE VERIFIED."""
    if isinstance(payload, dict) and payload.get("live_verified") is True:
        raise MemoryLayerError("live_claim", "autonomous app regression may not claim LIVE VERIFIED")


def require_trait_lab_autonomous_app_regression_provenance(*, agent_id: str, task_id: str) -> dict[str, Any]:
    """J02 — fail-closed without agent_id and task_id."""
    return require_trait_lab_autonomous_app_gate_provenance(agent_id=agent_id, task_id=task_id)


def require_trait_lab_autonomous_app_regression_no_live_ack(environ: Any = None) -> dict[str, Any]:
    """J03 — fail-closed when swarm live ack is present."""
    return require_trait_lab_autonomous_app_gate_no_live_ack(environ)


def _regression_body(mode: str) -> dict[str, Any]:
    return {
        "kind": _REGRESSION_KIND,
        "mode": mode,
        "live_verified": False,
    }


def _require_regression_mode(mode: Any) -> str:
    wanted = str(mode or "").strip()
    if wanted not in TRAIT_LAB_AUTONOMOUS_APP_REGRESSION_MODES:
        raise MemoryLayerError("invalid_mode", f"unknown regression mode {wanted or '<empty>'}")
    return wanted


def plan_trait_lab_autonomous_app_regression(mode: Any) -> dict[str, Any]:
    """J04 — unsigned regression plan (capture or compare)."""
    body = _regression_body(_require_regression_mode(mode))
    refuse_trait_lab_autonomous_app_regression_live(body)
    return body


def validate_trait_lab_autonomous_app_regression(plan: Any) -> dict[str, Any]:
    """J05 — fail-closed validation."""
    if not isinstance(plan, dict):
        raise MemoryLayerError("invalid_regression", "regression plan must be an object")
    refuse_trait_lab_autonomous_app_regression_live(plan)
    if plan.get("kind") not in {None, _REGRESSION_KIND}:
        raise MemoryLayerError("invalid_regression", "kind must be trait-lab-autonomous-app-regression")
    mode = _require_regression_mode(plan.get("mode"))
    return {**_regression_body(mode), "valid": True}


def sign_trait_lab_autonomous_app_regression(plan: Any) -> dict[str, Any]:
    """J06 — sign regression plan."""
    validated = validate_trait_lab_autonomous_app_regression(plan)
    body = _regression_body(validated["mode"])
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**body, "regression_sha256": hashlib.sha256(encoded).hexdigest(), "live_verified": False}


def verify_trait_lab_autonomous_app_regression(plan: Any) -> dict[str, Any]:
    """J07 — rematch regression_sha256."""
    if not isinstance(plan, dict):
        raise MemoryLayerError("invalid_regression", "regression plan must be an object")
    if plan.get("kind") != _REGRESSION_KIND:
        raise MemoryLayerError("invalid_regression", "kind must be trait-lab-autonomous-app-regression")
    refuse_trait_lab_autonomous_app_regression_live(plan)
    mode = _require_regression_mode(plan.get("mode"))
    sha = str(plan.get("regression_sha256") or "").strip().lower()
    if len(sha) != 64:
        raise MemoryLayerError("missing_regression_hash", "verify requires regression_sha256")
    body = _regression_body(mode)
    got = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if got != sha:
        raise MemoryLayerError("regression_mismatch", f"regression hashed {got[:12]} not {sha[:12]}")
    return {**body, "matched": True, "regression_sha256": sha, "live_verified": False}


def capture_trait_lab_autonomous_app_regression_baseline(
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
) -> dict[str, Any]:
    """J08 — run app gate and return signed baseline gate report."""
    gate = open_trait_lab_autonomous_app_gate(
        agent_id=agent_id, task_id=f"{task_id}:baseline", environ=environ, persist_artifact=False
    )
    if not gate.get("passed"):
        raise MemoryLayerError("gate_failed", "baseline capture requires passing gate")
    return verify_trait_lab_autonomous_app_gate_report(export_trait_lab_autonomous_app_gate_report(gate))


def capture_trait_lab_autonomous_app_regression_candidate(
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
) -> dict[str, Any]:
    """J09 — run app gate and return signed candidate gate report."""
    gate = open_trait_lab_autonomous_app_gate(
        agent_id=agent_id, task_id=f"{task_id}:candidate", environ=environ, persist_artifact=False
    )
    return verify_trait_lab_autonomous_app_gate_report(export_trait_lab_autonomous_app_gate_report(gate))


def compare_trait_lab_autonomous_app_regression_reports(baseline: Any, candidate: Any) -> dict[str, Any]:
    """J10 — compare baseline vs candidate gate reports."""
    left = verify_trait_lab_autonomous_app_gate_report(baseline)
    right = verify_trait_lab_autonomous_app_gate_report(candidate)
    cmp = compare_trait_lab_autonomous_app_gate_reports(left, right)
    no_regression = bool(left["passed"]) and bool(right["passed"]) and cmp["same_status"]
    return {
        **cmp,
        "baseline_gate_report_sha256": left["gate_report_sha256"],
        "candidate_gate_report_sha256": right["gate_report_sha256"],
        "no_regression": no_regression,
        "live_verified": False,
    }


def export_trait_lab_autonomous_app_regression_report(result: Any) -> dict[str, Any]:
    """J11 — signed regression outcome."""
    if not isinstance(result, dict):
        raise MemoryLayerError("invalid_regression", "regression result must be an object")
    refuse_trait_lab_autonomous_app_regression_live(result)
    plan = verify_trait_lab_autonomous_app_regression(result)
    baseline = result.get("baseline")
    candidate = result.get("candidate")
    compare: dict[str, Any] = {}
    if isinstance(baseline, dict) and isinstance(candidate, dict):
        compare = compare_trait_lab_autonomous_app_regression_reports(baseline, candidate)
    body = {
        "kind": _REPORT_KIND,
        "mode": plan["mode"],
        "baseline_gate_report_sha256": str((baseline or {}).get("gate_report_sha256") or ""),
        "candidate_gate_report_sha256": str((candidate or {}).get("gate_report_sha256") or ""),
        "no_regression": bool(compare.get("no_regression", result.get("no_regression", False))),
        "ok": bool(result.get("ok", compare.get("no_regression", False))),
        "live_verified": False,
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        **body,
        "regression_report_sha256": hashlib.sha256(encoded).hexdigest(),
        "live_verified": False,
    }


def verify_trait_lab_autonomous_app_regression_report(report: Any) -> dict[str, Any]:
    """J12 — rematch regression_report_sha256."""
    if not isinstance(report, dict):
        raise MemoryLayerError("invalid_regression", "regression report must be an object")
    if report.get("kind") != _REPORT_KIND:
        raise MemoryLayerError("invalid_regression", "kind must be trait-lab-autonomous-app-regression-report")
    refuse_trait_lab_autonomous_app_regression_live(report)
    sha = str(report.get("regression_report_sha256") or "").strip().lower()
    if len(sha) != 64:
        raise MemoryLayerError("missing_regression_report_hash", "verify requires regression_report_sha256")
    mode = _require_regression_mode(report.get("mode"))
    body = {
        "kind": _REPORT_KIND,
        "mode": mode,
        "baseline_gate_report_sha256": str(report.get("baseline_gate_report_sha256") or "").lower(),
        "candidate_gate_report_sha256": str(report.get("candidate_gate_report_sha256") or "").lower(),
        "no_regression": bool(report.get("no_regression")),
        "ok": bool(report.get("ok")),
        "live_verified": False,
    }
    got = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if got != sha:
        raise MemoryLayerError("regression_report_mismatch", f"report hashed {got[:12]} not {sha[:12]}")
    return {**body, "matched": True, "regression_report_sha256": sha, "live_verified": False}


def assert_trait_lab_autonomous_app_regression_ok(result: Any) -> dict[str, Any]:
    """J13 — fail-closed unless no regression detected."""
    report = verify_trait_lab_autonomous_app_regression_report(export_trait_lab_autonomous_app_regression_report(result))
    if not report["ok"] or not report["no_regression"]:
        raise MemoryLayerError("regression_failed", "app regression check failed")
    return {**report, "asserted": True, "live_verified": False}


def trait_lab_autonomous_app_regression_status(result: Any) -> str:
    """J14 — ready, blocked, or capture."""
    if not isinstance(result, dict):
        raise MemoryLayerError("invalid_regression", "regression status requires a result")
    if result.get("mode") == "capture" and result.get("baseline") and not result.get("candidate"):
        return "capture"
    if result.get("ok") and result.get("no_regression"):
        return "ready"
    return "blocked"


def trait_lab_autonomous_app_regression_digest(result: Any) -> str:
    """J15 — regression report SHA-256."""
    return str(export_trait_lab_autonomous_app_regression_report(result)["regression_report_sha256"])


def trait_lab_autonomous_app_regression_etag(result: Any) -> str:
    """J16 — short regression identity."""
    return trait_lab_autonomous_app_regression_digest(result)[:16]


def public_trait_lab_autonomous_app_regression_row(result: dict[str, Any]) -> dict[str, Any]:
    """J17 — stable regression summary."""
    report = export_trait_lab_autonomous_app_regression_report(result)
    return {
        "kind": _REPORT_KIND,
        "mode": report["mode"],
        "ok": report["ok"],
        "no_regression": report["no_regression"],
        "regression_report_sha256": report["regression_report_sha256"],
        "live_verified": False,
    }


def rematch_trait_lab_autonomous_app_regression_baseline(result: Any) -> dict[str, Any]:
    """J18 — re-verify baseline gate report embedded in result."""
    baseline = result.get("baseline")
    if not isinstance(baseline, dict):
        raise MemoryLayerError("missing_baseline", "regression has no baseline")
    return {**verify_trait_lab_autonomous_app_gate_report(baseline), "rematched": True, "live_verified": False}


def rematch_trait_lab_autonomous_app_regression_candidate(result: Any) -> dict[str, Any]:
    """J19 — re-verify candidate gate report embedded in result."""
    candidate = result.get("candidate")
    if not isinstance(candidate, dict):
        raise MemoryLayerError("missing_candidate", "regression has no candidate")
    return {**verify_trait_lab_autonomous_app_gate_report(candidate), "rematched": True, "live_verified": False}


def bundle_trait_lab_autonomous_app_regression_for_ci(result: Any) -> dict[str, Any]:
    """J20 — CI bundle for regression run."""
    report = verify_trait_lab_autonomous_app_regression_report(export_trait_lab_autonomous_app_regression_report(result))
    return {
        "regression": {
            "ok": report["ok"],
            "no_regression": report["no_regression"],
            "regression_report_sha256": report["regression_report_sha256"],
        },
        "live_verified": False,
    }


def compare_trait_lab_autonomous_app_regression_report_pair(left: Any, right: Any) -> dict[str, Any]:
    """J21 — compare two regression reports."""
    a = verify_trait_lab_autonomous_app_regression_report(left)
    b = verify_trait_lab_autonomous_app_regression_report(right)
    return {
        "same_ok": a["ok"] == b["ok"],
        "same_no_regression": a["no_regression"] == b["no_regression"],
        "live_verified": False,
    }


def trait_lab_autonomous_app_regression_row(result: Any) -> dict[str, Any]:
    """J22 — one-line regression metadata."""
    return public_trait_lab_autonomous_app_regression_row(result)


def _fact_id(regression_report_sha256: str) -> str:
    return f"{_FACT_PREFIX}{regression_report_sha256[:16]}"


def persist_trait_lab_autonomous_app_regression_artifact(
    store: MemoryStore,
    result: Any,
    *,
    agent_id: str,
    task_id: str,
) -> dict[str, Any]:
    """J23 — persist regression report."""
    require_trait_lab_autonomous_app_regression_provenance(agent_id=agent_id, task_id=task_id)
    report = verify_trait_lab_autonomous_app_regression_report(export_trait_lab_autonomous_app_regression_report(result))
    sha = str(report["regression_report_sha256"])
    write_verified(
        store,
        {
            "id": _fact_id(sha),
            "fact": f"autonomous app regression {sha} ok={report['ok']}",
            "how": f"persist_trait_lab_autonomous_app_regression_artifact {sha}",
            "confidence": 1.0,
            "source": sha,
            "agent_id": agent_id,
            "task_id": task_id,
            "kind": _REPORT_KIND,
            "ok": report["ok"],
            "regression_report_sha256": sha,
        },
    )
    record_task_step(
        store,
        task_id,
        "autonomous-app-regression",
        {"regression_report_sha256": sha},
        agent_id=agent_id,
    )
    return {
        "persisted": True,
        "regression_report_sha256": sha,
        "fact_id": _fact_id(sha),
        "live_verified": False,
    }


def trait_lab_autonomous_app_regression_contract_summary() -> dict[str, Any]:
    """J24 — hermetic catalog for verify scripts."""
    return {
        "gate_id": "memory-trait-lab-autonomous-app-regression-25",
        "ops_count": len(TRAIT_LAB_AUTONOMOUS_APP_REGRESSION_OPS),
        "modes": list(TRAIT_LAB_AUTONOMOUS_APP_REGRESSION_MODES),
        "hermetic_operator_ok": True,
        "live_verified": False,
    }


def open_trait_lab_autonomous_app_regression(
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
    baseline: Any = None,
    persist_artifact: bool = False,
) -> dict[str, Any]:
    """J25 — capture baseline or compare to provided baseline report."""
    if baseline is None:
        plan = sign_trait_lab_autonomous_app_regression(plan_trait_lab_autonomous_app_regression("capture"))
        base = capture_trait_lab_autonomous_app_regression_baseline(
            agent_id=agent_id, task_id=task_id, environ=environ
        )
        result = {
            **plan,
            "baseline": base,
            "candidate": None,
            "no_regression": True,
            "ok": True,
            "live_verified": False,
        }
    else:
        plan = sign_trait_lab_autonomous_app_regression(plan_trait_lab_autonomous_app_regression("compare"))
        base = verify_trait_lab_autonomous_app_gate_report(baseline)
        cand = capture_trait_lab_autonomous_app_regression_candidate(
            agent_id=agent_id, task_id=task_id, environ=environ
        )
        cmp = compare_trait_lab_autonomous_app_regression_reports(base, cand)
        result = {
            **plan,
            "baseline": base,
            "candidate": cand,
            **cmp,
            "ok": bool(cmp.get("no_regression")),
            "live_verified": False,
        }
        if not result["ok"]:
            raise MemoryLayerError("regression_failed", "candidate gate regressed vs baseline")
    report = export_trait_lab_autonomous_app_regression_report(result)
    artifact: dict[str, Any] = {"persisted": False}
    if persist_artifact and isinstance(result.get("candidate"), dict):
        gate = open_trait_lab_autonomous_app_gate(
            agent_id=agent_id, task_id=f"{task_id}:persist", environ=environ, persist_artifact=True
        )
        suite = gate.get("suite") if isinstance(gate.get("suite"), dict) else {}
        for srow in suite.get("runs") or []:
            if srow.get("mode") != "full":
                continue
            run = srow.get("run")
            if not isinstance(run, dict):
                continue
            from thinkbox.autonomous_stack_harness import export_trait_lab_autonomous_stack_smoke_report

            path = str(export_trait_lab_autonomous_stack_smoke_report(run).get("store_path") or "")
            if path:
                store = MemoryStore(path)
                try:
                    artifact = persist_trait_lab_autonomous_app_regression_artifact(
                        store, result, agent_id=agent_id, task_id=task_id
                    )
                finally:
                    store.close()
            break
    return {
        **result,
        "report": report,
        "artifact": artifact,
        "regression_open": True,
        "live_verified": False,
    }
