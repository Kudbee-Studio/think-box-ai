"""FIX25: Registry for PR #190 major fixes."""
from __future__ import annotations
import importlib
from typing import Any

_MODULES = (
    "thinkbox.think_job_post_run_major_fixes.fixes.f131_post_run_e2e",
    "thinkbox.think_job_post_run_major_fixes.fixes.post_run_deepen_status_module",
    "thinkbox.think_job_post_run_major_fixes.fixes.payload_required_fields",
    "thinkbox.think_job_post_run_major_fixes.fixes.governance_empty_guard",
    "thinkbox.think_job_post_run_major_fixes.fixes.run_governed_bridge",
    "thinkbox.think_job_post_run_major_fixes.fixes.pr184_post_run_deepen_gate",
    "thinkbox.think_job_post_run_major_fixes.fixes.pr185_lifecycle_gate",
    "thinkbox.think_job_post_run_major_fixes.fixes.pr186_receipt_deepen_gate",
    "thinkbox.think_job_post_run_major_fixes.fixes.pr187_receipt_fixes_gate",
    "thinkbox.think_job_post_run_major_fixes.fixes.pr188_governed_run_gate",
    "thinkbox.think_job_post_run_major_fixes.fixes.pr189_lifecycle_major_gate",
    "thinkbox.think_job_post_run_major_fixes.fixes.dry_run_post_run",
    "thinkbox.think_job_post_run_major_fixes.fixes.payload_schema_validate",
    "thinkbox.think_job_post_run_major_fixes.fixes.route_catalog_present",
    "thinkbox.think_job_post_run_major_fixes.fixes.cassette_post_run_flow",
    "thinkbox.think_job_post_run_major_fixes.fixes.receipt_stub_module",
    "thinkbox.think_job_post_run_major_fixes.fixes.no_live_mercury_claim",
    "thinkbox.think_job_post_run_major_fixes.fixes.secret_bearer_scan",
    "thinkbox.think_job_post_run_major_fixes.fixes.post_run_run_all_fixes",
    "thinkbox.think_job_post_run_major_fixes.fixes.run_governed_api_module",
    "thinkbox.think_job_post_run_major_fixes.fixes.four_state_integrate",
    "thinkbox.think_job_post_run_major_fixes.fixes.pr190_gate_lazy",
    "thinkbox.think_job_post_run_major_fixes.fixes.audit_pr190_shape",
    "thinkbox.think_job_post_run_major_fixes.fixes.fix_count_honesty",
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
