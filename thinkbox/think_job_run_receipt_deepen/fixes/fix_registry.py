"""FIX25: Registry for PR #187 major fixes."""
from __future__ import annotations
import importlib
from typing import Any

_MODULES = (
    "thinkbox.think_job_run_receipt_deepen.fixes.receipt_id_format_guard",
    "thinkbox.think_job_run_receipt_deepen.fixes.session_experiment_required",
    "thinkbox.think_job_run_receipt_deepen.fixes.governance_nonempty_guard",
    "thinkbox.think_job_run_receipt_deepen.fixes.sqlite_path_fail_closed",
    "thinkbox.think_job_run_receipt_deepen.fixes.artifact_dir_default",
    "thinkbox.think_job_run_receipt_deepen.fixes.redact_token_fields",
    "thinkbox.think_job_run_receipt_deepen.fixes.idempotency_header_case",
    "thinkbox.think_job_run_receipt_deepen.fixes.etag_weak_prefix",
    "thinkbox.think_job_run_receipt_deepen.fixes.pagination_cap",
    "thinkbox.think_job_run_receipt_deepen.fixes.cassette_receipt_steps",
    "thinkbox.think_job_run_receipt_deepen.fixes.replay_shape_valid",
    "thinkbox.think_job_run_receipt_deepen.fixes.f133_harness_present",
    "thinkbox.think_job_run_receipt_deepen.fixes.f185_pairing_check",
    "thinkbox.think_job_run_receipt_deepen.fixes.f184_receipt_handoff",
    "thinkbox.think_job_run_receipt_deepen.fixes.status_path_prefix",
    "thinkbox.think_job_run_receipt_deepen.fixes.stream_path_prefix",
    "thinkbox.think_job_run_receipt_deepen.fixes.dry_run_skips_persist",
    "thinkbox.think_job_run_receipt_deepen.fixes.dashboard_think_jobs",
    "thinkbox.think_job_run_receipt_deepen.fixes.secret_scan_helper",
    "thinkbox.think_job_run_receipt_deepen.fixes.run_job_bridge_engine",
    "thinkbox.think_job_run_receipt_deepen.fixes.pr186_features_manifest",
    "thinkbox.think_job_run_receipt_deepen.fixes.four_state_honesty",
    "thinkbox.think_job_run_receipt_deepen.fixes.validate_receipt_shape_fix",
    "thinkbox.think_job_run_receipt_deepen.fixes.audit_pr187_shape",
)

def run_all_fixes() -> dict[str, Any]:
    results = []
    for name in _MODULES:
        results.append(importlib.import_module(name).apply_fix())
    results.append(apply_fix())
    ok = all(r.get("live_api_called") is False for r in results)
    return {"fix_count": len(results), "all_hermetic": ok, "live_api_called": False}

def apply_fix() -> dict[str, Any]:
    return {"fix_id": "FIX25", "module_count": len(_MODULES), "live_api_called": False}
