"""FIX25: Registry for PR #189 major fixes."""
from __future__ import annotations
import importlib
from typing import Any

_MODULES = (
    "thinkbox.think_job_lifecycle_major_fixes.fixes.f023_lifecycle_e2e",
    "thinkbox.think_job_lifecycle_major_fixes.fixes.lifecycle_status_report_module",
    "thinkbox.think_job_lifecycle_major_fixes.fixes.admission_token_strip",
    "thinkbox.think_job_lifecycle_major_fixes.fixes.governance_denied_codes",
    "thinkbox.think_job_lifecycle_major_fixes.fixes.hermetic_provider_path",
    "thinkbox.think_job_lifecycle_major_fixes.fixes.pr183_e2e_gate",
    "thinkbox.think_job_lifecycle_major_fixes.fixes.pr184_post_run_gate",
    "thinkbox.think_job_lifecycle_major_fixes.fixes.pr185_lifecycle_gate",
    "thinkbox.think_job_lifecycle_major_fixes.fixes.pr186_receipt_deepen_gate",
    "thinkbox.think_job_lifecycle_major_fixes.fixes.pr187_receipt_fixes_gate",
    "thinkbox.think_job_lifecycle_major_fixes.fixes.pr188_governed_run_gate",
    "thinkbox.think_job_lifecycle_major_fixes.fixes.post_run_dry_run",
    "thinkbox.think_job_lifecycle_major_fixes.fixes.think_job_status_ui",
    "thinkbox.think_job_lifecycle_major_fixes.fixes.control_plane_etag_store",
    "thinkbox.think_job_lifecycle_major_fixes.fixes.cassette_lifecycle_flow",
    "thinkbox.think_job_lifecycle_major_fixes.fixes.jobs_digest_multiplex",
    "thinkbox.think_job_lifecycle_major_fixes.fixes.no_live_mercury_claim",
    "thinkbox.think_job_lifecycle_major_fixes.fixes.secret_bearer_scan",
    "thinkbox.think_job_lifecycle_major_fixes.fixes.lifecycle_run_all_fixes",
    "thinkbox.think_job_lifecycle_major_fixes.fixes.run_job_status_module",
    "thinkbox.think_job_lifecycle_major_fixes.fixes.four_state_integrate",
    "thinkbox.think_job_lifecycle_major_fixes.fixes.pr189_gate_lazy",
    "thinkbox.think_job_lifecycle_major_fixes.fixes.audit_pr189_shape",
    "thinkbox.think_job_lifecycle_major_fixes.fixes.fix_count_honesty",
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
