"""FIX25: Registry integrates FIX01-FIX24."""
from __future__ import annotations
import importlib
from typing import Any

_MODULES = (
    "thinkbox.think_job_lifecycle_fixes.fixes.lifecycle_status_mapping",
    "thinkbox.think_job_lifecycle_fixes.fixes.started_status_alias",
    "thinkbox.think_job_lifecycle_fixes.fixes.canonical_job_id_field",
    "thinkbox.think_job_lifecycle_fixes.fixes.receipt_id_bridge",
    "thinkbox.think_job_lifecycle_fixes.fixes.pr183_pairing_gate_check",
    "thinkbox.think_job_lifecycle_fixes.fixes.goal_whitespace_guard",
    "thinkbox.think_job_lifecycle_fixes.fixes.dry_run_no_receipt",
    "thinkbox.think_job_lifecycle_fixes.fixes.if_match_precondition_stub",
    "thinkbox.think_job_lifecycle_fixes.fixes.admission_governance_error_split",
    "thinkbox.think_job_lifecycle_fixes.fixes.cassette_401_replay",
    "thinkbox.think_job_lifecycle_fixes.fixes.whitespace_admission_token",
    "thinkbox.think_job_lifecycle_fixes.fixes.ledger_think_job_id",
    "thinkbox.think_job_lifecycle_fixes.fixes.background_pending_count",
    "thinkbox.think_job_lifecycle_fixes.fixes.receipt_db_fail_closed",
    "thinkbox.think_job_lifecycle_fixes.fixes.poll_interval_crossref",
    "thinkbox.think_job_lifecycle_fixes.fixes.stream_schema_version",
    "thinkbox.think_job_lifecycle_fixes.fixes.digest_sorted_keys",
    "thinkbox.think_job_lifecycle_fixes.fixes.not_found_envelope",
    "thinkbox.think_job_lifecycle_fixes.fixes.sse_frame_bound_replay",
    "thinkbox.think_job_lifecycle_fixes.fixes.auth_fragment_secret_scan",
    "thinkbox.think_job_lifecycle_fixes.fixes.query_key_no_leak",
    "thinkbox.think_job_lifecycle_fixes.fixes.dashboard_redact_synonyms",
    "thinkbox.think_job_lifecycle_fixes.fixes.spine_lazy_hook",
    "thinkbox.think_job_lifecycle_fixes.fixes.audit_pass_shape",
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
