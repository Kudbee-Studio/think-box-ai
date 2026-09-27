"""Hermetic Trait Lab autonomous integration major (K01–K25).

Orchestrates app gate + optional regression for application CI manifests.
No live APIs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from core.memory.store import MemoryStore
from thinkbox.autonomous_app_gate import (
    export_trait_lab_autonomous_app_gate_report,
    open_trait_lab_autonomous_app_gate,
    require_trait_lab_autonomous_app_gate_no_live_ack,
    require_trait_lab_autonomous_app_gate_provenance,
    verify_trait_lab_autonomous_app_gate_report,
)
from thinkbox.autonomous_app_regression import (
    export_trait_lab_autonomous_app_regression_report,
    open_trait_lab_autonomous_app_regression,
    require_trait_lab_autonomous_app_regression_no_live_ack,
    verify_trait_lab_autonomous_app_regression_report,
)
from thinkbox.memory_layers import MemoryLayerError, record_task_step, write_verified

_INTEGRATION_KIND = "trait-lab-autonomous-integration-major"
_REPORT_KIND = "trait-lab-autonomous-integration-major-report"
_FACT_PREFIX = "trait-lab-auto-integration-major-"

TRAIT_LAB_AUTONOMOUS_INTEGRATION_MAJOR_OPS: tuple[str, ...] = (
    "refuse_live",
    "require_provenance",
    "require_no_live_ack",
    "plan_integration",
    "validate_integration",
    "sign_integration",
    "verify_integration",
    "list_layers",
    "layer_ok",
    "run_gate_layer",
    "run_regression_layer",
    "export_integration_report",
    "verify_integration_report",
    "assert_integration_ok",
    "integration_status",
    "digest",
    "etag",
    "public_row",
    "manifest_layers",
    "bundle_for_ci",
    "compare_integration_reports",
    "integration_row",
    "persist_integration_artifact",
    "contract_summary",
    "open_integration_major",
)

TRAIT_LAB_AUTONOMOUS_INTEGRATION_MAJOR_LAYERS: tuple[str, ...] = ("app_gate", "app_regression")
TRAIT_LAB_AUTONOMOUS_INTEGRATION_MAJOR_MODES: tuple[str, ...] = ("gate", "gate_regression")


def refuse_trait_lab_autonomous_integration_major_live(payload: Any) -> None:
    """K01 — integration payloads may not claim LIVE VERIFIED."""
    if isinstance(payload, dict) and payload.get("live_verified") is True:
        raise MemoryLayerError(
            "live_claim",
            "autonomous integration major may not claim LIVE VERIFIED",
        )


def require_trait_lab_autonomous_integration_major_provenance(*, agent_id: str, task_id: str) -> dict[str, Any]:
    """K02 — fail-closed without agent_id and task_id."""
    return require_trait_lab_autonomous_app_gate_provenance(agent_id=agent_id, task_id=task_id)


def require_trait_lab_autonomous_integration_major_no_live_ack(environ: Any = None) -> dict[str, Any]:
    """K03 — fail-closed when swarm live ack is present."""
    require_trait_lab_autonomous_app_regression_no_live_ack(environ)
    return require_trait_lab_autonomous_app_gate_no_live_ack(environ)


def _integration_body(mode: str, layers: list[str]) -> dict[str, Any]:
    return {
        "kind": _INTEGRATION_KIND,
        "mode": mode,
        "layers": layers,
        "count": len(layers),
        "live_verified": False,
    }


def _require_integration_mode(mode: Any) -> str:
    wanted = str(mode or "").strip()
    if wanted not in TRAIT_LAB_AUTONOMOUS_INTEGRATION_MAJOR_MODES:
        raise MemoryLayerError("invalid_mode", f"unknown integration mode {wanted or '<empty>'}")
    return wanted


def _layers_for_mode(mode: str) -> list[str]:
    if mode == "gate":
        return ["app_gate"]
    return list(TRAIT_LAB_AUTONOMOUS_INTEGRATION_MAJOR_LAYERS)


def plan_trait_lab_autonomous_integration_major(mode: Any = "gate_regression") -> dict[str, Any]:
    """K04 — unsigned integration plan."""
    m = _require_integration_mode(mode)
    body = _integration_body(m, _layers_for_mode(m))
    refuse_trait_lab_autonomous_integration_major_live(body)
    return body


def validate_trait_lab_autonomous_integration_major(plan: Any) -> dict[str, Any]:
    """K05 — fail-closed validation."""
    if not isinstance(plan, dict):
        raise MemoryLayerError("invalid_integration", "integration plan must be an object")
    refuse_trait_lab_autonomous_integration_major_live(plan)
    if plan.get("kind") not in {None, _INTEGRATION_KIND}:
        raise MemoryLayerError("invalid_integration", "kind must be trait-lab-autonomous-integration-major")
    mode = _require_integration_mode(plan.get("mode"))
    layers = plan.get("layers")
    if not isinstance(layers, list):
        layers = _layers_for_mode(mode)
    allowed = set(TRAIT_LAB_AUTONOMOUS_INTEGRATION_MAJOR_LAYERS)
    names: list[str] = []
    for item in layers:
        name = str(item or "").strip()
        if name not in allowed:
            raise MemoryLayerError("invalid_layer", f"unknown integration layer {name or '<empty>'}")
        names.append(name)
    if mode == "gate" and names != ["app_gate"]:
        raise MemoryLayerError("invalid_layer", "gate mode requires only app_gate layer")
    if mode == "gate_regression" and set(names) != set(TRAIT_LAB_AUTONOMOUS_INTEGRATION_MAJOR_LAYERS):
        raise MemoryLayerError("invalid_layer", "gate_regression mode requires app_gate and app_regression")
    return {**_integration_body(mode, names), "valid": True}


def sign_trait_lab_autonomous_integration_major(plan: Any) -> dict[str, Any]:
    """K06 — sign integration plan."""
    validated = validate_trait_lab_autonomous_integration_major(plan)
    body = _integration_body(validated["mode"], validated["layers"])
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**body, "integration_sha256": hashlib.sha256(encoded).hexdigest(), "live_verified": False}


def verify_trait_lab_autonomous_integration_major(plan: Any) -> dict[str, Any]:
    """K07 — rematch integration_sha256."""
    if not isinstance(plan, dict):
        raise MemoryLayerError("invalid_integration", "integration plan must be an object")
    if plan.get("kind") != _INTEGRATION_KIND:
        raise MemoryLayerError("invalid_integration", "kind must be trait-lab-autonomous-integration-major")
    refuse_trait_lab_autonomous_integration_major_live(plan)
    mode = _require_integration_mode(plan.get("mode"))
    layers = _require_gate_layers(plan.get("layers"), mode)
    sha = str(plan.get("integration_sha256") or "").strip().lower()
    if len(sha) != 64:
        raise MemoryLayerError("missing_integration_hash", "verify requires integration_sha256")
    body = _integration_body(mode, layers)
    got = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if got != sha:
        raise MemoryLayerError("integration_mismatch", f"integration hashed {got[:12]} not {sha[:12]}")
    return {**body, "matched": True, "integration_sha256": sha, "live_verified": False}


def _require_gate_layers(layers: Any, mode: str) -> list[str]:
    validated = validate_trait_lab_autonomous_integration_major(
        {"kind": _INTEGRATION_KIND, "mode": mode, "layers": layers}
    )
    return list(validated["layers"])


def list_trait_lab_autonomous_integration_major_layers(plan: Any) -> list[str]:
    """K08 — layer names from signed plan."""
    return list(verify_trait_lab_autonomous_integration_major(plan)["layers"])


def trait_lab_autonomous_integration_major_layer_ok(run: Any, layer: str) -> bool:
    """K09 — true when named layer result is ok."""
    wanted = str(layer or "").strip()
    for row in run.get("layer_results") or []:
        if isinstance(row, dict) and row.get("layer") == wanted:
            return bool(row.get("ok"))
    return False


def run_trait_lab_autonomous_integration_major_gate_layer(
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
) -> dict[str, Any]:
    """K10 — run app gate layer only."""
    gate = open_trait_lab_autonomous_app_gate(
        agent_id=agent_id, task_id=f"{task_id}:gate", environ=environ, persist_artifact=False
    )
    report = export_trait_lab_autonomous_app_gate_report(gate)
    return {
        "layer": "app_gate",
        "ok": bool(gate.get("ok")),
        "gate_report_sha256": report["gate_report_sha256"],
        "gate": gate,
        "live_verified": False,
    }


def run_trait_lab_autonomous_integration_major_regression_layer(
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
    baseline: Any = None,
) -> dict[str, Any]:
    """K11 — run app regression layer (capture or compare)."""
    reg = open_trait_lab_autonomous_app_regression(
        agent_id=agent_id,
        task_id=f"{task_id}:regression",
        environ=environ,
        baseline=baseline,
        persist_artifact=False,
    )
    report = export_trait_lab_autonomous_app_regression_report(reg)
    return {
        "layer": "app_regression",
        "ok": bool(reg.get("ok")),
        "regression_report_sha256": report["regression_report_sha256"],
        "regression": reg,
        "live_verified": False,
    }


def export_trait_lab_autonomous_integration_major_report(run: Any) -> dict[str, Any]:
    """K12 — signed integration report."""
    if not isinstance(run, dict):
        raise MemoryLayerError("invalid_integration", "integration report requires a run")
    refuse_trait_lab_autonomous_integration_major_live(run)
    plan = verify_trait_lab_autonomous_integration_major(run)
    layer_results = run.get("layer_results")
    if not isinstance(layer_results, list):
        raise MemoryLayerError("invalid_integration", "layer_results must be a list")
    ok = all(bool(r.get("ok")) for r in layer_results if isinstance(r, dict))
    body = {
        "kind": _REPORT_KIND,
        "mode": plan["mode"],
        "layers": plan["layers"],
        "layer_results": layer_results,
        "count": len(layer_results),
        "ok": ok,
        "status": "ready" if ok else "blocked",
        "integration_sha256": plan["integration_sha256"],
        "live_verified": False,
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        **body,
        "integration_report_sha256": hashlib.sha256(encoded).hexdigest(),
        "live_verified": False,
    }


def verify_trait_lab_autonomous_integration_major_report(report: Any) -> dict[str, Any]:
    """K13 — rematch integration_report_sha256."""
    if not isinstance(report, dict):
        raise MemoryLayerError("invalid_integration", "integration report must be an object")
    if report.get("kind") != _REPORT_KIND:
        raise MemoryLayerError("invalid_integration", "kind must be trait-lab-autonomous-integration-major-report")
    refuse_trait_lab_autonomous_integration_major_live(report)
    sha = str(report.get("integration_report_sha256") or "").strip().lower()
    if len(sha) != 64:
        raise MemoryLayerError("missing_integration_report_hash", "verify requires integration_report_sha256")
    mode = _require_integration_mode(report.get("mode"))
    layers = _require_gate_layers(report.get("layers"), mode)
    layer_results = report.get("layer_results") or []
    ok = bool(report.get("ok"))
    body = {
        "kind": _REPORT_KIND,
        "mode": mode,
        "layers": layers,
        "layer_results": layer_results,
        "count": int(report.get("count") or len(layer_results)),
        "ok": ok,
        "status": str(report.get("status") or ""),
        "integration_sha256": str(report.get("integration_sha256") or "").lower(),
        "live_verified": False,
    }
    got = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if got != sha:
        raise MemoryLayerError(
            "integration_report_mismatch",
            f"integration report hashed {got[:12]} not {sha[:12]}",
        )
    return {**body, "matched": True, "integration_report_sha256": sha, "live_verified": False}


def assert_trait_lab_autonomous_integration_major_ok(run: Any) -> dict[str, Any]:
    """K14 — fail-closed unless all layers ok."""
    report = verify_trait_lab_autonomous_integration_major_report(
        export_trait_lab_autonomous_integration_major_report(run)
    )
    if not report["ok"]:
        raise MemoryLayerError("integration_failed", "autonomous integration major did not pass")
    return {**report, "asserted": True, "live_verified": False}


def integration_trait_lab_autonomous_major_status(run: Any) -> str:
    """K15 — ready or blocked."""
    report = export_trait_lab_autonomous_integration_major_report(run)
    return str(report.get("status") or "blocked")


def trait_lab_autonomous_integration_major_digest(run: Any) -> str:
    """K16 — integration report SHA-256."""
    return str(export_trait_lab_autonomous_integration_major_report(run)["integration_report_sha256"])


def trait_lab_autonomous_integration_major_etag(run: Any) -> str:
    """K17 — short integration identity."""
    return trait_lab_autonomous_integration_major_digest(run)[:16]


def public_trait_lab_autonomous_integration_major_row(run: dict[str, Any]) -> dict[str, Any]:
    """K18 — stable summary for dashboards."""
    report = export_trait_lab_autonomous_integration_major_report(run)
    return {
        "kind": _REPORT_KIND,
        "mode": report["mode"],
        "ok": report["ok"],
        "status": report["status"],
        "integration_report_sha256": report["integration_report_sha256"],
        "live_verified": False,
    }


def manifest_trait_lab_autonomous_integration_major_layers(plan: Any) -> dict[str, Any]:
    """K19 — SDK-friendly layer manifest."""
    signed = verify_trait_lab_autonomous_integration_major(plan)
    return {
        "integration_sha256": signed["integration_sha256"],
        "mode": signed["mode"],
        "layers": [
            {"name": name, "order": idx, "live_verified": False}
            for idx, name in enumerate(signed["layers"])
        ],
        "live_verified": False,
    }


def bundle_trait_lab_autonomous_integration_major_for_ci(run: Any) -> dict[str, Any]:
    """K20 — JSON-friendly CI bundle."""
    report = verify_trait_lab_autonomous_integration_major_report(
        export_trait_lab_autonomous_integration_major_report(run)
    )
    return {
        "integration": verify_trait_lab_autonomous_integration_major(run),
        "report": {
            "ok": report["ok"],
            "status": report["status"],
            "integration_report_sha256": report["integration_report_sha256"],
            "layer_results": [
                {"layer": r.get("layer"), "ok": r.get("ok")} for r in report["layer_results"] if isinstance(r, dict)
            ],
        },
        "live_verified": False,
    }


def compare_trait_lab_autonomous_integration_major_reports(left: Any, right: Any) -> dict[str, Any]:
    """K21 — compare two integration reports."""
    a = verify_trait_lab_autonomous_integration_major_report(left)
    b = verify_trait_lab_autonomous_integration_major_report(right)
    return {
        "same_ok": a["ok"] == b["ok"],
        "same_mode": a["mode"] == b["mode"],
        "same_count": a["count"] == b["count"],
        "live_verified": False,
    }


def trait_lab_autonomous_integration_major_row(run: Any) -> dict[str, Any]:
    """K22 — one-line integration metadata."""
    return public_trait_lab_autonomous_integration_major_row(run)


def _fact_id(integration_report_sha256: str) -> str:
    return f"{_FACT_PREFIX}{integration_report_sha256[:16]}"


def persist_trait_lab_autonomous_integration_major_artifact(
    store: MemoryStore,
    run: Any,
    *,
    agent_id: str,
    task_id: str,
) -> dict[str, Any]:
    """K23 — persist integration report on workspace store."""
    require_trait_lab_autonomous_integration_major_provenance(agent_id=agent_id, task_id=task_id)
    report = export_trait_lab_autonomous_integration_major_report(run)
    sha = report["integration_report_sha256"]
    write_verified(
        store,
        _fact_id(sha),
        report,
        layer="task",
        metadata={
            "kind": _REPORT_KIND,
            "integration_report_sha256": sha,
            "ok": report["ok"],
        },
    )
    record_task_step(
        store,
        task_id,
        "autonomous-integration-major",
        {"integration_report_sha256": sha},
        agent_id=agent_id,
    )
    return {
        "persisted": True,
        "integration_report_sha256": sha,
        "fact_id": _fact_id(sha),
        "live_verified": False,
    }


def trait_lab_autonomous_integration_major_contract_summary() -> dict[str, Any]:
    """K24 — hermetic catalog for verify scripts."""
    return {
        "gate_id": "memory-trait-lab-autonomous-integration-major-25",
        "ops_count": len(TRAIT_LAB_AUTONOMOUS_INTEGRATION_MAJOR_OPS),
        "modes": list(TRAIT_LAB_AUTONOMOUS_INTEGRATION_MAJOR_MODES),
        "layers": list(TRAIT_LAB_AUTONOMOUS_INTEGRATION_MAJOR_LAYERS),
        "hermetic_operator_ok": True,
        "live_verified": False,
    }


def open_trait_lab_autonomous_integration_major(
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
    mode: str = "gate_regression",
    regression_baseline: Any = None,
    persist_artifact: bool = False,
) -> dict[str, Any]:
    """K25 — run gate and optional regression layers for application CI."""
    require_trait_lab_autonomous_integration_major_provenance(agent_id=agent_id, task_id=task_id)
    require_trait_lab_autonomous_integration_major_no_live_ack(environ)
    plan = sign_trait_lab_autonomous_integration_major(plan_trait_lab_autonomous_integration_major(mode))
    layer_results: list[dict[str, Any]] = []
    gate_row = run_trait_lab_autonomous_integration_major_gate_layer(
        agent_id=agent_id, task_id=task_id, environ=environ
    )
    layer_results.append(gate_row)
    regression_row: dict[str, Any] | None = None
    if "app_regression" in plan["layers"]:
        baseline = regression_baseline
        if baseline is None and gate_row.get("ok"):
            gate_report = verify_trait_lab_autonomous_app_gate_report(
                export_trait_lab_autonomous_app_gate_report(gate_row["gate"])
            )
            baseline = gate_report
        regression_row = run_trait_lab_autonomous_integration_major_regression_layer(
            agent_id=agent_id,
            task_id=task_id,
            environ=environ,
            baseline=baseline,
        )
        layer_results.append(regression_row)
    ok = all(r["ok"] for r in layer_results)
    result = {
        **plan,
        "layer_results": layer_results,
        "ok": ok,
        "status": "ready" if ok else "blocked",
        "live_verified": False,
    }
    report = export_trait_lab_autonomous_integration_major_report(result)
    artifact: dict[str, Any] = {"persisted": False}
    if persist_artifact and gate_row.get("ok"):
        gate = gate_row.get("gate")
        if isinstance(gate, dict):
            suite = gate.get("suite")
            if isinstance(suite, dict):
                from thinkbox.autonomous_stack_harness import export_trait_lab_autonomous_stack_smoke_report

                for srow in suite.get("runs") or []:
                    if not isinstance(srow, dict) or srow.get("mode") != "full" or not srow.get("ok"):
                        continue
                    full_run = srow.get("run")
                    if not isinstance(full_run, dict):
                        continue
                    path = str(export_trait_lab_autonomous_stack_smoke_report(full_run).get("store_path") or "")
                    if not path:
                        continue
                    store = MemoryStore(path)
                    try:
                        artifact = persist_trait_lab_autonomous_integration_major_artifact(
                            store, result, agent_id=agent_id, task_id=task_id
                        )
                    finally:
                        store.close()
                    break
    return {
        **result,
        "report": report,
        "artifact": artifact,
        "integration_open": True,
        "live_verified": False,
    }
