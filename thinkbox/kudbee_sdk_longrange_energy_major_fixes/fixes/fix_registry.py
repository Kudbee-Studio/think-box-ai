"""FIX25: fix registry (PR #194)."""
from __future__ import annotations

import importlib
from typing import Any

from thinkbox.kudbee_sdk_longrange_energy_major_fixes.negotiation import EXPECTED_FIX_COUNT

_MODULES = (
    "thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.pr193_gate_lazy",
    "thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.lr_config_fail_closed",
    "thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.lr_dry_run_transport",
    "thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.lr_webhook_signature_dry_run",
    "thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.lr_federation_energy_router",
    "thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.lr_session_bind_tags",
    "thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.lr_task_cancel_hermetic",
    "thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.lr_hop_cursor_roundtrip",
    "thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.lr_cassette_replay",
    "thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.lr_fixture_library",
    "thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.lr_observability_reset",
    "thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.lr_health_readiness_tier",
    "thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.lr_transport_route_miss",
    "thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.lr_client_capabilities",
    "thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.lr_integrate_registry",
    "thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.lr_route_catalog",
    "thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.lr_secret_allowlist",
    "thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.lr_conservation_ledger_fix",
    "thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.lr_energy_loop_mesh_fix",
    "thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.deepen_packs_gate",
    "thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.typescript_longrange_energy",
    "thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.no_live_mercury_claim",
    "thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.four_state_integrate",
    "thinkbox.kudbee_sdk_longrange_energy_major_fixes.fixes.fix_count_honesty",
)


def run_all_fixes() -> dict[str, Any]:
    results = []
    for mod in _MODULES:
        results.append(importlib.import_module(mod).apply_fix())
    results.append(apply_fix())
    ok = all(r.get("live_api_called") is False for r in results)
    return {"fix_count": len(results), "all_hermetic": ok, "live_api_called": False}


def apply_fix() -> dict[str, Any]:
    return {
        "fix_id": "FIX25",
        "ok": len(_MODULES) + 1 == EXPECTED_FIX_COUNT,
        "live_api_called": False,
    }
