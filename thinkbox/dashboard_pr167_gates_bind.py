"""Dashboard bind of PR #167 gates (PR #168 theme C).

Display/bind only — maps #167 theme gate ids to dashboard slot statuses hermetically.
Does not earn LIVE VERIFIED.
"""

from __future__ import annotations

from typing import Any, Mapping

from thinkbox.kilo_api_ops_harden_post166 import GATE_ID as THEME_B_GATE
from thinkbox.kilo_dashboard_pr166_gates_bind import GATE_ID as THEME_C_PRIOR_GATE
from thinkbox.kilo_live_proof_operator_audit_flip_deepen import GATE_ID as THEME_A_GATE
from thinkbox.kilo_pr167_combined_post166_lane import GATE_ID as PR167_UMBRELLA
from thinkbox.kilo_swarm_governance_post166_deepen import GATE_ID as THEME_D_GATE

__all__ = (
    "DASHBOARD_PR167_BIND_LABEL",
    "DASHBOARD_PR167_BIND_VERSION",
    "PR167_THEME_GATE_IDS",
    "bind_pr167_gates_to_slots",
    "dashboard_pr167_bind_contract_snippet",
    "slot_status_for_gate",
)

DASHBOARD_PR167_BIND_LABEL = "dashboard-pr167-gates-bind"
DASHBOARD_PR167_BIND_VERSION = "1.0.0"

PR167_THEME_GATE_IDS: tuple[str, ...] = (
    THEME_A_GATE,
    THEME_B_GATE,
    THEME_C_PRIOR_GATE,
    THEME_D_GATE,
)

_SLOT_PREFIX = "kilo-pr167-"


def slot_status_for_gate(gate_id: str, *, hermetic_ok: bool) -> dict[str, Any]:
    """One dashboard slot row for a PR #167 theme gate."""
    return {
        "slot_id": f"{_SLOT_PREFIX}{gate_id}",
        "bound_gate_id": gate_id,
        "pr167_umbrella_gate": PR167_UMBRELLA,
        "occupancy": "bound" if hermetic_ok else "stale",
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "display_only": True,
    }


def bind_pr167_gates_to_slots(
    gate_hermetic_ok: Mapping[str, bool],
) -> list[dict[str, Any]]:
    """Bind PR #167 theme gates to slot statuses (hermetic inputs only)."""
    rows: list[dict[str, Any]] = []
    for gate_id in PR167_THEME_GATE_IDS:
        ok = bool(gate_hermetic_ok.get(gate_id))
        rows.append(slot_status_for_gate(gate_id, hermetic_ok=ok))
    return rows


def dashboard_pr167_bind_contract_snippet() -> dict[str, Any]:
    return {
        "label": DASHBOARD_PR167_BIND_LABEL,
        "version": DASHBOARD_PR167_BIND_VERSION,
        "theme_gate_count": len(PR167_THEME_GATE_IDS),
        "pr167_umbrella_gate_id": PR167_UMBRELLA,
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
    }
