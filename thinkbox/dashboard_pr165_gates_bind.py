"""Dashboard bind of PR #165 gates (PR #166 theme C).

Display/bind only — maps #165 theme gate ids to dashboard slot statuses hermetically.
Does not earn LIVE VERIFIED.
"""

from __future__ import annotations

from typing import Any, Mapping

from thinkbox.kilo_control_plane_post164_deepen import GATE_ID as THEME_B_GATE
from thinkbox.kilo_dashboard_slots import GATE_ID as DASHBOARD_SLOTS_GATE
from thinkbox.kilo_live_smoke_audit_flip_harden import GATE_ID as THEME_A_GATE
from thinkbox.kilo_pr165_combined_harden_era_chronicle import GATE_ID as PR165_UMBRELLA
from thinkbox.kilo_receipt_chain_end_link_season_harden import GATE_ID as THEME_C_GATE

__all__ = (
    "DASHBOARD_PR165_BIND_LABEL",
    "DASHBOARD_PR165_BIND_VERSION",
    "PR165_THEME_GATE_IDS",
    "bind_pr165_gates_to_slots",
    "dashboard_pr165_bind_contract_snippet",
    "slot_status_for_gate",
)

DASHBOARD_PR165_BIND_LABEL = "dashboard-pr165-gates-bind"
DASHBOARD_PR165_BIND_VERSION = "1.0.0"

PR165_THEME_GATE_IDS: tuple[str, ...] = (
    THEME_A_GATE,
    THEME_B_GATE,
    THEME_C_GATE,
    PR165_UMBRELLA,
)

_SLOT_PREFIX = "kilo-pr165-"


def slot_status_for_gate(gate_id: str, *, hermetic_ok: bool) -> dict[str, Any]:
    """One dashboard slot row for a PR #165 theme gate."""
    return {
        "slot_id": f"{_SLOT_PREFIX}{gate_id}",
        "bound_gate_id": gate_id,
        "dashboard_slots_gate": DASHBOARD_SLOTS_GATE,
        "occupancy": "bound" if hermetic_ok else "stale",
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "display_only": True,
    }


def bind_pr165_gates_to_slots(
    gate_hermetic_ok: Mapping[str, bool],
) -> list[dict[str, Any]]:
    """Bind PR #165 theme gates to slot statuses (hermetic inputs only)."""
    rows: list[dict[str, Any]] = []
    for gate_id in PR165_THEME_GATE_IDS:
        ok = bool(gate_hermetic_ok.get(gate_id))
        rows.append(slot_status_for_gate(gate_id, hermetic_ok=ok))
    return rows


def dashboard_pr165_bind_contract_snippet() -> dict[str, Any]:
    return {
        "label": DASHBOARD_PR165_BIND_LABEL,
        "version": DASHBOARD_PR165_BIND_VERSION,
        "theme_gate_count": len(PR165_THEME_GATE_IDS),
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
    }
