"""FIX20: Integrate and run all PR #183 major fixes."""

from __future__ import annotations

import importlib
from typing import Any

_FIX_MODULES: tuple[str, ...] = (
    "thinkbox.think_job_e2e_deepen.fixes.lazy_run_job_schema",
    "thinkbox.think_job_e2e_deepen.fixes.e2e_scaffold_bridge",
    "thinkbox.think_job_e2e_deepen.fixes.dashboard_emit_shape",
    "thinkbox.think_job_e2e_deepen.fixes.f023_lifecycle_align",
    "thinkbox.think_job_e2e_deepen.fixes.sse_frame_bounds",
    "thinkbox.think_job_e2e_deepen.fixes.poll_interval_guard",
    "thinkbox.think_job_e2e_deepen.fixes.jobs_digest_stub",
    "thinkbox.think_job_e2e_deepen.fixes.etag_tab_stub",
    "thinkbox.think_job_e2e_deepen.fixes.deep_link_hash_mode",
    "thinkbox.think_job_e2e_deepen.fixes.bounded_step_runner",
    "thinkbox.think_job_e2e_deepen.fixes.cancel_terminal_guard",
    "thinkbox.think_job_e2e_deepen.fixes.failure_taxonomy_map",
    "thinkbox.think_job_e2e_deepen.fixes.proof_hash_stub",
    "thinkbox.think_job_e2e_deepen.fixes.ledger_metadata_shape",
    "thinkbox.think_job_e2e_deepen.fixes.nested_e2e_catalog",
    "thinkbox.think_job_e2e_deepen.fixes.checklist_honesty",
    "thinkbox.think_job_e2e_deepen.fixes.receipt_watch_empty_guard",
    "thinkbox.think_job_e2e_deepen.fixes.stream_hub_reset",
    "thinkbox.think_job_e2e_deepen.fixes.control_plane_route_stub",
)


def list_fix_modules() -> tuple[str, ...]:
    return _FIX_MODULES


def run_all_fixes() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for mod_name in _FIX_MODULES:
        mod = importlib.import_module(mod_name)
        results.append(mod.apply_fix())
    results.append(apply_fix())
    ok = all(r.get("live_api_called") is False for r in results)
    return {
        "fix_count": len(results),
        "results": results,
        "all_hermetic": ok,
        "live_api_called": False,
    }


def apply_fix() -> dict[str, Any]:
    return {
        "fix_id": "FIX20",
        "prior_fix_modules": len(_FIX_MODULES),
        "live_api_called": False,
    }
