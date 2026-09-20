"""Founder policy waiver — governance-gated org-memory only."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from thinkbox.admission import AdmissionGate
from thinkbox.org_memory_receipts import OrgMemoryReceiptStore

PIPELINE_POLICY_WAIVER_CAPABILITY = "pipeline:founder:policy_waiver"


def has_active_policy_waiver(store: OrgMemoryReceiptStore, pr_number: int, *, limit: int = 30) -> bool:
    """True if a waiver receipt exists and is not superseded by a later policy denial."""
    for row in store.query(pr_number=pr_number, limit=limit):
        action = str(row.get("action") or "")
        if action == "merge_policy_denied":
            return False
        if action == "founder_policy_waiver":
            return True
    return False


class PolicyWaiverService:
    """Record a founder policy waiver (never grants GitHub merge)."""

    def __init__(self, store: OrgMemoryReceiptStore, gate: AdmissionGate, agent_id: str) -> None:
        self._store = store
        self._gate = gate
        self._agent_id = agent_id

    def grant_waiver(
        self,
        pr_number: int,
        *,
        branch: str,
        governance_token: str,
        reason: str = "founder_accepted_risk",
    ) -> dict[str, Any]:
        decision = self._gate.authorize(
            governance_token,
            self._agent_id,
            PIPELINE_POLICY_WAIVER_CAPABILITY,
            metadata={"pr_number": pr_number, "reason": reason},
        )
        if not decision.allowed:
            return {
                "granted": False,
                "detail": decision.reason,
                "evidence_label": "simulated",
            }
        self._store.append_lifecycle(
            run_id=f"policy_waiver_{pr_number}",
            pr_number=pr_number,
            branch=branch or "unknown",
            from_state="BLOCKED",
            to_state="READY_FOR_CLOSE",
            action="founder_policy_waiver",
            result="success",
            evidence_label="simulated",
            evidence={
                "reason": reason,
                "agent_id": self._agent_id,
                "github_merge": False,
                "auto_merge": False,
                "granted_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {"granted": True, "detail": "ok", "evidence_label": "simulated"}
