"""Swarm / governance deepen post-#166 (PR #167 theme D).

Hermetic admission/evidence shape checks after PR #166. No live Mercury/Box HTTP.
"""

from __future__ import annotations

from typing import Any, Mapping

from thinkbox.kilo_governance_evidence import GATE_ID as GOV_EVIDENCE_GATE
from thinkbox.kilo_governance_evidence_live_proof_readiness import (
    GATE_ID as GOV_READINESS_GATE,
)
from thinkbox.kilo_pr166_combined_post165_lane import GATE_ID as PR166_GATE_ID
from thinkbox.kilo_swarm_governance_post165_deepen import GATE_ID as POST165_SWARM_GATE
from thinkbox.kilo_swarm_instrumentation import GATE_ID as SWARM_GATE

__all__ = (
    "SWARM_GOV_POST166_LABEL",
    "SWARM_GOV_POST166_VERSION",
    "admission_evidence_shape_ok",
    "swarm_governance_post166_contract_snippet",
    "swarm_governance_post166_markers_present",
)

SWARM_GOV_POST166_LABEL = "swarm-governance-post166-deepen"
SWARM_GOV_POST166_VERSION = "1.0.0"

_REQUIRED_SHAPE_KEYS: tuple[str, ...] = (
    "gate_id",
    "hermetic_operator_ok",
    "live_verified",
    "live_api_called",
    "four_state_max",
)


def admission_evidence_shape_ok(summary: Mapping[str, Any]) -> bool:
    """Fail-closed shape check for governance/swarm contract summaries."""
    for key in _REQUIRED_SHAPE_KEYS:
        if key == "live_verified":
            continue
        if key not in summary:
            return False
    if summary.get("live_verified") is True:
        return False
    if summary.get("live_api_called") is True:
        return False
    fs = summary.get("four_state_max")
    if fs in ("LIVE_VERIFIED", "PRODUCTION_READY"):
        return False
    return True


def swarm_governance_post166_markers_present(text: str) -> bool:
    needles = (
        SWARM_GOV_POST166_LABEL,
        SWARM_GATE,
        GOV_EVIDENCE_GATE,
        PR166_GATE_ID,
        POST165_SWARM_GATE,
    )
    return all(n in text for n in needles)


def swarm_governance_post166_contract_snippet() -> dict[str, Any]:
    return {
        "label": SWARM_GOV_POST166_LABEL,
        "version": SWARM_GOV_POST166_VERSION,
        "prior_gate_ids": [
            SWARM_GATE,
            GOV_EVIDENCE_GATE,
            GOV_READINESS_GATE,
            POST165_SWARM_GATE,
            PR166_GATE_ID,
        ],
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
    }
