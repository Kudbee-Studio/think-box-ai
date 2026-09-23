"""Swarm / governance deepen post-#168 (PR #169 theme D).

Hermetic admission/evidence shape checks after PR #168. No live Mercury/Box HTTP.
"""

from __future__ import annotations

from typing import Any, Mapping

from thinkbox.kilo_governance_evidence import GATE_ID as GOV_EVIDENCE_GATE
from thinkbox.kilo_governance_evidence_live_proof_readiness import (
    GATE_ID as GOV_READINESS_GATE,
)
from thinkbox.kilo_pr168_combined_post167_lane import GATE_ID as PR168_GATE_ID
from thinkbox.kilo_swarm_governance_post167_deepen import GATE_ID as POST167_SWARM_GATE
from thinkbox.kilo_swarm_instrumentation import GATE_ID as SWARM_GATE

__all__ = (
    "SWARM_GOV_POST168_LABEL",
    "SWARM_GOV_POST168_VERSION",
    "admission_evidence_shape_ok",
    "swarm_governance_post168_contract_snippet",
    "swarm_governance_post168_markers_present",
)

SWARM_GOV_POST168_LABEL = "swarm-governance-post168-deepen"
SWARM_GOV_POST168_VERSION = "1.0.0"

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


def swarm_governance_post168_markers_present(text: str) -> bool:
    needles = (
        SWARM_GOV_POST168_LABEL,
        SWARM_GATE,
        GOV_EVIDENCE_GATE,
        PR168_GATE_ID,
        POST167_SWARM_GATE,
    )
    return all(n in text for n in needles)


def swarm_governance_post168_contract_snippet() -> dict[str, Any]:
    return {
        "gate_id": SWARM_GOV_POST168_LABEL,
        "label": SWARM_GOV_POST168_LABEL,
        "version": SWARM_GOV_POST168_VERSION,
        "hermetic_operator_ok": False,
        "prior_gate_ids": [POST167_SWARM_GATE],
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
    }
