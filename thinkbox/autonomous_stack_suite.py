"""Hermetic Trait Lab autonomous stack suite (V01–V25).

Runs dry, run, and full stack smoke in one signed suite for CI and app regression.
No live APIs.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from core.memory.store import MemoryStore
from thinkbox.autonomous_stack_harness import (
    TRAIT_LAB_AUTONOMOUS_STACK_SMOKE_MODES,
    assert_trait_lab_autonomous_stack_smoke_ok,
    export_trait_lab_autonomous_stack_smoke_report,
    persist_trait_lab_autonomous_stack_smoke_artifact,
    plan_trait_lab_autonomous_stack_smoke,
    require_trait_lab_autonomous_stack_harness_no_live_ack,
    require_trait_lab_autonomous_stack_harness_provenance,
    run_trait_lab_autonomous_stack_smoke,
    sign_trait_lab_autonomous_stack_smoke,
    verify_trait_lab_autonomous_stack_smoke_report,
)
from thinkbox.memory_layers import MemoryLayerError, record_task_step, write_verified

_SUITE_KIND = "trait-lab-autonomous-stack-suite"
_SUITE_REPORT_KIND = "trait-lab-autonomous-stack-suite-report"
_SUITE_FACT_PREFIX = "trait-lab-auto-stack-suite-"

TRAIT_LAB_AUTONOMOUS_STACK_SUITE_OPS: tuple[str, ...] = (
    "refuse_live",
    "require_provenance",
    "require_no_live_ack",
    "plan_suite",
    "validate_suite",
    "sign_suite",
    "verify_suite",
    "run_suite",
    "suite_status",
    "export_suite_report",
    "verify_suite_report",
    "assert_suite_ok",
    "list_runs",
    "run_ok",
    "digest",
    "etag",
    "public_row",
    "rematch_full_smoke",
    "count_runs",
    "filter_by_mode",
    "bundle_for_ci",
    "compare_suite_reports",
    "suite_row",
    "persist_suite_artifact",
    "open_stack_suite",
)

DEFAULT_SUITE_MODES: tuple[str, ...] = ("dry", "run", "full")


def refuse_trait_lab_autonomous_stack_suite_live(payload: Any) -> None:
    """V01 — suite payloads may not claim LIVE VERIFIED."""
    if isinstance(payload, dict) and payload.get("live_verified") is True:
        raise MemoryLayerError("live_claim", "autonomous stack suite may not claim LIVE VERIFIED")


def require_trait_lab_autonomous_stack_suite_provenance(*, agent_id: str, task_id: str) -> dict[str, Any]:
    """V02 — fail-closed without agent_id and task_id."""
    return require_trait_lab_autonomous_stack_harness_provenance(agent_id=agent_id, task_id=task_id)


def require_trait_lab_autonomous_stack_suite_no_live_ack(environ: Any = None) -> dict[str, Any]:
    """V03 — fail-closed when swarm live ack is present."""
    return require_trait_lab_autonomous_stack_harness_no_live_ack(environ)


def _suite_body(modes: list[str]) -> dict[str, Any]:
    return {
        "kind": _SUITE_KIND,
        "modes": modes,
        "count": len(modes),
        "live_verified": False,
    }


def _require_suite_modes(modes: Any) -> list[str]:
    if not isinstance(modes, list) or not modes:
        raise MemoryLayerError("missing_mode", "suite requires at least one smoke mode")
    allowed = set(TRAIT_LAB_AUTONOMOUS_STACK_SMOKE_MODES)
    names: list[str] = []
    for item in modes:
        name = str(item or "").strip()
        if name not in allowed:
            raise MemoryLayerError("invalid_mode", f"unknown suite mode {name or '<empty>'}")
        names.append(name)
    return names


def plan_trait_lab_autonomous_stack_suite(modes: Any = None) -> dict[str, Any]:
    """V04 — build an unsigned stack suite plan (default dry, run, full)."""
    selected = _require_suite_modes(list(modes) if modes is not None else list(DEFAULT_SUITE_MODES))
    body = _suite_body(selected)
    refuse_trait_lab_autonomous_stack_suite_live(body)
    return body


def validate_trait_lab_autonomous_stack_suite(plan: Any) -> dict[str, Any]:
    """V05 — fail-closed check of a suite plan."""
    if not isinstance(plan, dict):
        raise MemoryLayerError("invalid_suite", "stack suite plan must be an object")
    refuse_trait_lab_autonomous_stack_suite_live(plan)
    if plan.get("kind") not in {None, _SUITE_KIND}:
        raise MemoryLayerError("invalid_suite", "kind must be trait-lab-autonomous-stack-suite")
    modes = _require_suite_modes(plan.get("modes"))
    return {**_suite_body(modes), "valid": True}


def sign_trait_lab_autonomous_stack_suite(plan: Any) -> dict[str, Any]:
    """V06 — sign a validated suite plan."""
    validated = validate_trait_lab_autonomous_stack_suite(plan)
    body = _suite_body(validated["modes"])
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**body, "suite_sha256": hashlib.sha256(encoded).hexdigest(), "live_verified": False}


def verify_trait_lab_autonomous_stack_suite(plan: Any) -> dict[str, Any]:
    """V07 — rematch suite_sha256."""
    if not isinstance(plan, dict):
        raise MemoryLayerError("invalid_suite", "stack suite plan must be an object")
    if plan.get("kind") != _SUITE_KIND:
        raise MemoryLayerError("invalid_suite", "kind must be trait-lab-autonomous-stack-suite")
    refuse_trait_lab_autonomous_stack_suite_live(plan)
    modes = _require_suite_modes(plan.get("modes"))
    sha = str(plan.get("suite_sha256") or "").strip().lower()
    if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
        raise MemoryLayerError("missing_suite_hash", "verify requires suite_sha256")
    body = _suite_body(modes)
    got = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if got != sha:
        raise MemoryLayerError("suite_mismatch", f"suite hashed {got[:12]} not {sha[:12]}")
    return {**body, "matched": True, "suite_sha256": sha, "live_verified": False}


def run_trait_lab_autonomous_stack_suite(
    plan: Any,
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
) -> dict[str, Any]:
    """V08 — execute each smoke mode in plan order."""
    require_trait_lab_autonomous_stack_suite_provenance(agent_id=agent_id, task_id=task_id)
    require_trait_lab_autonomous_stack_suite_no_live_ack(environ)
    signed = sign_trait_lab_autonomous_stack_suite(plan)
    runs: list[dict[str, Any]] = []
    for idx, mode in enumerate(signed["modes"]):
        smoke_plan = sign_trait_lab_autonomous_stack_smoke(plan_trait_lab_autonomous_stack_smoke(mode))
        ran = run_trait_lab_autonomous_stack_smoke(
            smoke_plan,
            agent_id=agent_id,
            task_id=f"{task_id}:{mode}:{idx}",
            environ=environ,
        )
        runs.append(
            {
                "mode": mode,
                "ok": bool(ran.get("ok")),
                "status": ran.get("status"),
                "run": ran,
                "report": export_trait_lab_autonomous_stack_smoke_report(ran),
                "live_verified": False,
            }
        )
    ok = all(row["ok"] for row in runs)
    status = suite_trait_lab_autonomous_stack_status({"runs": runs, "ok": ok})
    return {
        **signed,
        "runs": runs,
        "status": status,
        "ok": ok,
        "live_verified": False,
    }


def suite_trait_lab_autonomous_stack_status(result: Any) -> str:
    """V09 — ready when all runs ok, blocked otherwise, dry_run if only dry modes ran."""
    if not isinstance(result, dict):
        raise MemoryLayerError("invalid_suite", "suite status requires a result")
    refuse_trait_lab_autonomous_stack_suite_live(result)
    runs = result.get("runs")
    if not isinstance(runs, list) or not runs:
        raise MemoryLayerError("invalid_suite", "suite status requires runs")
    if all(bool(r.get("ok")) for r in runs if isinstance(r, dict)):
        modes = [str(r.get("mode") or "") for r in runs if isinstance(r, dict)]
        if modes == ["dry"] or (len(modes) == 1 and modes[0] == "dry"):
            return "dry_run"
        return "ready"
    return "blocked"


def export_trait_lab_autonomous_stack_suite_report(suite_run: Any) -> dict[str, Any]:
    """V10 — signed aggregate of per-mode smoke reports."""
    if not isinstance(suite_run, dict):
        raise MemoryLayerError("invalid_suite", "suite report requires a suite run")
    refuse_trait_lab_autonomous_stack_suite_live(suite_run)
    verified = verify_trait_lab_autonomous_stack_suite(suite_run)
    runs = suite_run.get("runs")
    if not isinstance(runs, list):
        raise MemoryLayerError("invalid_suite", "runs must be a list")
    summaries: list[dict[str, Any]] = []
    for row in runs:
        if not isinstance(row, dict):
            continue
        report = row.get("report")
        if not isinstance(report, dict):
            report = export_trait_lab_autonomous_stack_smoke_report(row.get("run") or row)
        summaries.append(
            {
                "mode": str(row.get("mode") or report.get("mode") or ""),
                "ok": bool(row.get("ok", report.get("ok"))),
                "status": str(row.get("status") or report.get("status") or ""),
                "report_sha256": str(report.get("report_sha256") or ""),
                "live_verified": False,
            }
        )
    body = {
        "kind": _SUITE_REPORT_KIND,
        "modes": verified["modes"],
        "runs": summaries,
        "count": len(summaries),
        "ok": bool(suite_run.get("ok", all(s["ok"] for s in summaries))),
        "status": suite_trait_lab_autonomous_stack_status(suite_run),
        "live_verified": False,
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**body, "suite_report_sha256": hashlib.sha256(encoded).hexdigest(), "live_verified": False}


def verify_trait_lab_autonomous_stack_suite_report(report: Any) -> dict[str, Any]:
    """V11 — rematch suite_report_sha256."""
    if not isinstance(report, dict):
        raise MemoryLayerError("invalid_suite", "suite report must be an object")
    if report.get("kind") != _SUITE_REPORT_KIND:
        raise MemoryLayerError("invalid_suite", "kind must be trait-lab-autonomous-stack-suite-report")
    refuse_trait_lab_autonomous_stack_suite_live(report)
    if not isinstance(report.get("runs"), list):
        raise MemoryLayerError("invalid_suite", "runs must be a list")
    sha = str(report.get("suite_report_sha256") or "").strip().lower()
    if len(sha) != 64:
        raise MemoryLayerError("missing_suite_report_hash", "verify requires suite_report_sha256")
    body = {
        "kind": _SUITE_REPORT_KIND,
        "modes": _require_suite_modes(report.get("modes")),
        "runs": report["runs"],
        "count": len(report["runs"]),
        "ok": bool(report.get("ok", True)),
        "status": str(report.get("status") or ""),
        "live_verified": False,
    }
    got = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if got != sha:
        raise MemoryLayerError("suite_report_mismatch", f"suite report hashed {got[:12]} not {sha[:12]}")
    return {**body, "matched": True, "suite_report_sha256": sha, "live_verified": False}


def assert_trait_lab_autonomous_stack_suite_ok(suite_run: Any) -> dict[str, Any]:
    """V12 — fail-closed when any suite run is not ok."""
    report = verify_trait_lab_autonomous_stack_suite_report(export_trait_lab_autonomous_stack_suite_report(suite_run))
    if not report["ok"]:
        raise MemoryLayerError("suite_failed", "stack suite is not ok")
    for row in suite_run.get("runs") or []:
        if isinstance(row, dict) and row.get("run"):
            assert_trait_lab_autonomous_stack_smoke_ok(row["run"])
    return {**report, "asserted": True, "live_verified": False}


def list_trait_lab_autonomous_stack_suite_runs(suite_run: Any) -> list[dict[str, Any]]:
    """V13 — per-mode run summaries."""
    report = export_trait_lab_autonomous_stack_suite_report(suite_run)
    return list(report["runs"])


def trait_lab_autonomous_stack_suite_run_ok(suite_run: Any, mode: str) -> bool:
    """V14 — true when the named mode run succeeded."""
    wanted = str(mode or "").strip()
    if wanted not in TRAIT_LAB_AUTONOMOUS_STACK_SMOKE_MODES:
        raise MemoryLayerError("invalid_mode", f"unknown mode {wanted or '<empty>'}")
    for row in list_trait_lab_autonomous_stack_suite_runs(suite_run):
        if row.get("mode") == wanted:
            return bool(row.get("ok"))
    return False


def trait_lab_autonomous_stack_suite_digest(suite_run: Any) -> str:
    """V15 — suite report SHA-256."""
    return str(export_trait_lab_autonomous_stack_suite_report(suite_run)["suite_report_sha256"])


def trait_lab_autonomous_stack_suite_etag(suite_run: Any) -> str:
    """V16 — short suite identity."""
    return trait_lab_autonomous_stack_suite_digest(suite_run)[:16]


def public_trait_lab_autonomous_stack_suite_row(suite_run: dict[str, Any]) -> dict[str, Any]:
    """V17 — stable suite summary."""
    report = export_trait_lab_autonomous_stack_suite_report(suite_run)
    return {
        "kind": _SUITE_REPORT_KIND,
        "count": report["count"],
        "ok": report["ok"],
        "status": report["status"],
        "suite_report_sha256": report["suite_report_sha256"],
        "live_verified": False,
    }


def rematch_trait_lab_autonomous_stack_suite_full_smoke(suite_run: Any) -> dict[str, Any]:
    """V18 — re-open full-mode harness and verify flow rematch path."""
    full_row = None
    for row in suite_run.get("runs") or []:
        if isinstance(row, dict) and row.get("mode") == "full":
            full_row = row
            break
    if full_row is None:
        raise MemoryLayerError("missing_mode", "suite has no full mode run")
    run = full_row.get("run")
    if not isinstance(run, dict):
        raise MemoryLayerError("invalid_suite", "full run missing")
    report = export_trait_lab_autonomous_stack_smoke_report(run)
    path = str(report.get("store_path") or "").strip()
    if not path:
        raise MemoryLayerError("missing_store", "full smoke has no store_path")
    from thinkbox.autonomous_stack_harness import rematch_trait_lab_autonomous_stack_flow_receipt

    store = MemoryStore(path)
    try:
        return rematch_trait_lab_autonomous_stack_flow_receipt(store, run.get("result") or run)
    finally:
        store.close()


def count_trait_lab_autonomous_stack_suite_runs(suite_run: Any) -> int:
    """V19 — number of mode runs in suite."""
    return int(export_trait_lab_autonomous_stack_suite_report(suite_run)["count"])


def filter_trait_lab_autonomous_stack_suite_by_mode(suite_run: Any, mode: str) -> dict[str, Any]:
    """V20 — subset suite report to one mode."""
    wanted = str(mode or "").strip()
    if wanted not in TRAIT_LAB_AUTONOMOUS_STACK_SMOKE_MODES:
        raise MemoryLayerError("invalid_mode", f"unknown mode {wanted or '<empty>'}")
    full = export_trait_lab_autonomous_stack_suite_report(suite_run)
    rows = [row for row in full["runs"] if row.get("mode") == wanted]
    if not rows:
        raise MemoryLayerError("missing_mode", f"suite has no run for mode {wanted}")
    body = {
        "kind": _SUITE_REPORT_KIND,
        "modes": [wanted],
        "runs": rows,
        "count": len(rows),
        "ok": all(bool(r.get("ok")) for r in rows),
        "status": str(rows[0].get("status") or ""),
        "live_verified": False,
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**body, "suite_report_sha256": hashlib.sha256(encoded).hexdigest(), "live_verified": False}


def bundle_trait_lab_autonomous_stack_for_ci(suite_run: Any) -> dict[str, Any]:
    """V21 — JSON-friendly CI bundle (modes + ok flags only)."""
    report = verify_trait_lab_autonomous_stack_suite_report(export_trait_lab_autonomous_stack_suite_report(suite_run))
    return {
        "suite": verify_trait_lab_autonomous_stack_suite(suite_run),
        "report": {
            "ok": report["ok"],
            "status": report["status"],
            "suite_report_sha256": report["suite_report_sha256"],
            "runs": report["runs"],
        },
        "live_verified": False,
    }


def compare_trait_lab_autonomous_stack_suite_reports(left: Any, right: Any) -> dict[str, Any]:
    """V22 — compare two suite reports."""
    a = verify_trait_lab_autonomous_stack_suite_report(left)
    b = verify_trait_lab_autonomous_stack_suite_report(right)
    return {
        "same_ok": a["ok"] == b["ok"],
        "same_count": a["count"] == b["count"],
        "same_status": a["status"] == b["status"],
        "live_verified": False,
    }


def trait_lab_autonomous_stack_suite_row(suite_run: Any) -> dict[str, Any]:
    """V23 — one-line suite metadata."""
    return public_trait_lab_autonomous_stack_suite_row(suite_run)


def _suite_fact_id(suite_report_sha256: str) -> str:
    return f"{_SUITE_FACT_PREFIX}{suite_report_sha256[:16]}"


def persist_trait_lab_autonomous_stack_suite_artifact(
    store: MemoryStore,
    suite_run: Any,
    *,
    agent_id: str,
    task_id: str,
) -> dict[str, Any]:
    """V24 — persist suite report on the full-mode workspace store."""
    require_trait_lab_autonomous_stack_suite_provenance(agent_id=agent_id, task_id=task_id)
    report = verify_trait_lab_autonomous_stack_suite_report(export_trait_lab_autonomous_stack_suite_report(suite_run))
    sha = str(report["suite_report_sha256"])
    write_verified(
        store,
        {
            "id": _suite_fact_id(sha),
            "fact": f"autonomous stack suite {sha} modes={report['count']}",
            "how": f"persist_trait_lab_autonomous_stack_suite_artifact {sha}",
            "confidence": 1.0,
            "source": sha,
            "agent_id": agent_id,
            "task_id": task_id,
            "kind": _SUITE_REPORT_KIND,
            "count": report["count"],
            "ok": report["ok"],
            "suite_report_sha256": sha,
        },
    )
    record_task_step(
        store,
        task_id,
        "autonomous-stack-suite",
        {"suite_report_sha256": sha, "ok": report["ok"]},
        agent_id=agent_id,
    )
    return {
        "persisted": True,
        "suite_report_sha256": sha,
        "fact_id": _suite_fact_id(sha),
        "live_verified": False,
    }


def open_trait_lab_autonomous_stack_suite(
    *,
    agent_id: str,
    task_id: str,
    environ: Any = None,
    modes: Any = None,
    persist_artifact: bool = True,
) -> dict[str, Any]:
    """V25 — default dry+run+full suite; persist suite + full smoke artifacts when enabled."""
    plan = sign_trait_lab_autonomous_stack_suite(plan_trait_lab_autonomous_stack_suite(modes))
    ran = run_trait_lab_autonomous_stack_suite(
        plan, agent_id=agent_id, task_id=task_id, environ=environ
    )
    report = export_trait_lab_autonomous_stack_suite_report(ran)
    suite_artifact: dict[str, Any] = {"persisted": False}
    if persist_artifact:
        for row in ran.get("runs") or []:
            if not isinstance(row, dict) or row.get("mode") != "full" or not row.get("ok"):
                continue
            smoke_report = row.get("report")
            if not isinstance(smoke_report, dict):
                continue
            path = str(smoke_report.get("store_path") or "").strip()
            if not path:
                continue
            store = MemoryStore(path)
            try:
                smoke_run = row.get("run")
                if isinstance(smoke_run, dict):
                    persist_trait_lab_autonomous_stack_smoke_artifact(
                        store, smoke_run, agent_id=agent_id, task_id=task_id
                    )
                suite_artifact = persist_trait_lab_autonomous_stack_suite_artifact(
                    store, ran, agent_id=agent_id, task_id=task_id
                )
            finally:
                store.close()
            break
    return {
        **ran,
        "report": report,
        "suite_artifact": suite_artifact,
        "suite_open": True,
        "live_verified": False,
    }
