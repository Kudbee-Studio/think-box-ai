"""EXP26: expansion pack registry."""
from __future__ import annotations

import importlib
from typing import Any

from thinkbox.kudbee_sdk_followup_w3_expansion.negotiation import EXPECTED_EXPANSION_PACK_COUNT

_MODULES = (
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.long_range_link_open",
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.long_range_link_ping",
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.long_range_hop_budget",
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.long_range_correlation_chain",
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.long_range_mesh_stub",
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.long_range_keepalive_pulse",
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.long_range_backoff_curve",
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.long_range_connection_pool",
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.energy_loop_open",
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.energy_loop_quantize_unit",
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.energy_flow_rate_meter",
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.energy_conservation_check",
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.energy_idle_drain_model",
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.energy_throughput_stub",
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.energy_loop_closure_verifier",
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.energy_free_flow_regulator",
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.energy_session_attribution",
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.energy_task_budget_cap",
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.quantitative_metrics_snapshot",
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.long_range_energy_bridge",
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.twin_energy_receipt_stub",
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.federation_long_path",
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.pr192_expansion_gate_bind",
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.expansion_count_honesty",
    "thinkbox.kudbee_sdk_followup_w3_expansion.packs.no_live_energy_claim",
)


def run_all_packs() -> dict[str, Any]:
    results = []
    for name in _MODULES:
        results.append(importlib.import_module(name).activate_pack())
    results.append(activate_pack())
    ok = all(r.get("live_api_called") is False for r in results)
    return {
        "pack_count": len(results),
        "all_hermetic": ok,
        "live_api_called": False,
        "theme": "long_range_connections_and_energy_loops",
    }


def activate_pack() -> dict[str, Any]:
    return {
        "pack_id": "EXP26",
        "ok": len(_MODULES) + 1 == EXPECTED_EXPANSION_PACK_COUNT,
        "live_api_called": False,
    }
