"""Gate summary bridge for PR #182 (F14)."""

from __future__ import annotations

from typing import Any

from thinkbox.kilo_pr182_receipt_chain_deepen import GATE_ID, PR_NUMBER, receipt_chain_deepen_contract_summary


def deepen_gate_summary() -> dict[str, Any]:
    summary = receipt_chain_deepen_contract_summary()
    return {
        "gate_id": GATE_ID,
        "pr_number": PR_NUMBER,
        "hermetic_operator_ok": summary.get("hermetic_operator_ok"),
        "live_verified": False,
        "live_api_called": False,
        "four_state_max": "TEST_VERIFIED",
        "violation_count": summary.get("violation_count"),
    }
