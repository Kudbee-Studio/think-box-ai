from __future__ import annotations
import importlib
from typing import Any
_MODULES = (
    "thinkbox.think_job_post_run_deepen.fixes.payload_required_fields",
    "thinkbox.think_job_post_run_deepen.fixes.governance_empty_guard",
    "thinkbox.think_job_post_run_deepen.fixes.auth_prefix_guard",
    "thinkbox.think_job_post_run_deepen.fixes.admission_token_guard",
    "thinkbox.think_job_post_run_deepen.fixes.envelope_shape",
    "thinkbox.think_job_post_run_deepen.fixes.idempotency_duplicate",
    "thinkbox.think_job_post_run_deepen.fixes.rate_limit_cap",
    "thinkbox.think_job_post_run_deepen.fixes.redact_token_field",
    "thinkbox.think_job_post_run_deepen.fixes.f131_paths_exist",
)
def run_all_fixes() -> dict[str, Any]:
    results = []
    for name in _MODULES:
        results.append(importlib.import_module(name).apply_fix())
    results.append(apply_fix())
    ok = all(r.get("live_api_called") is False for r in results)
    return {"fix_count": len(results), "all_hermetic": ok, "live_api_called": False}
def apply_fix() -> dict[str, Any]:
    return {"fix_id": "FIX10", "module_count": len(_MODULES), "live_api_called": False}
