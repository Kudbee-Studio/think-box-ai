"""PR rollup helpers shared across pipeline modules (breaks import cycles)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class EvidenceLabelCounts:
    verified: int = 0
    simulated: int = 0
    rejected: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "verified": self.verified,
            "simulated": self.simulated,
            "rejected": self.rejected,
        }


@dataclass
class PRPipelineSummary:
    pr_number: int
    branch: str
    lifecycle_state: str
    evidence_counts: EvidenceLabelCounts
    admission_denied_count: int
    last_ci: Optional[dict[str, Any]]
    blocked_reasons: list[str] = field(default_factory=list)
    merge_request_status: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return {
            "pr_number": self.pr_number,
            "branch": self.branch,
            "lifecycle_state": self.lifecycle_state,
            "evidence_counts": self.evidence_counts.to_dict(),
            "admission_denied_count": self.admission_denied_count,
            "last_ci": self.last_ci,
            "blocked_reasons": self.blocked_reasons,
            "merge_request_status": self.merge_request_status,
        }


def _label_counts(receipts: list[dict[str, Any]]) -> EvidenceLabelCounts:
    counts = EvidenceLabelCounts()
    for row in receipts:
        label = str(row.get("evidence_label") or "simulated").lower()
        if label == "verified":
            counts.verified += 1
        elif label == "rejected":
            counts.rejected += 1
        else:
            counts.simulated += 1
    return counts


def _collect_blocked_reasons(receipts: list[dict[str, Any]]) -> list[str]:
    reasons: list[str] = []
    seen: set[str] = set()
    for row in receipts:
        action = str(row.get("action") or "")
        result = str(row.get("result") or "")
        evidence = row.get("evidence") or {}
        if action == "admission_denied":
            reason = str(evidence.get("admission_reason") or "admission_denied")
        elif action == "merge_requested" and result == "blocked":
            reason = str(evidence.get("reason") or "founder_approval_required")
        elif action == "merge_request_denied":
            reason = str(evidence.get("admission_reason") or evidence.get("reason") or "merge_denied")
        elif result == "blocked":
            reason = str(evidence.get("reason") or action or "blocked")
        else:
            continue
        if reason not in seen:
            seen.add(reason)
            reasons.append(reason)
    return reasons


def _last_ci_observation(receipts: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    for row in receipts:
        if str(row.get("action") or "") != "ci_status_observed":
            continue
        evidence = row.get("evidence") or {}
        return {
            "workflow": evidence.get("workflow"),
            "conclusion": evidence.get("conclusion"),
            "ci_run_id": evidence.get("ci_run_id"),
            "timestamp": row.get("timestamp"),
            "evidence_label": row.get("evidence_label"),
        }
    return None


def _merge_request_status(receipts: list[dict[str, Any]]) -> str:
    for row in receipts:
        action = str(row.get("action") or "")
        if action == "founder_merge_requested":
            return "queued"
        if action == "merge_requested":
            return "blocked" if row.get("result") == "blocked" else str(row.get("result") or "unknown")
        if action == "merge_request_denied":
            return "denied"
    return "none"


def summarize_pr_from_receipts(
    pr_number: int,
    receipts_newest_first: list[dict[str, Any]],
) -> PRPipelineSummary:
    """Build a pipeline summary from receipts (newest-first order)."""
    branch = ""
    lifecycle_state = "UNKNOWN"
    if receipts_newest_first:
        branch = str(receipts_newest_first[0].get("branch") or "")
        lifecycle_state = str(receipts_newest_first[0].get("to_state") or "UNKNOWN")

    admission_denied = sum(
        1 for r in receipts_newest_first if str(r.get("action") or "") == "admission_denied"
    )
    return PRPipelineSummary(
        pr_number=pr_number,
        branch=branch,
        lifecycle_state=lifecycle_state,
        evidence_counts=_label_counts(receipts_newest_first),
        admission_denied_count=admission_denied,
        last_ci=_last_ci_observation(receipts_newest_first),
        blocked_reasons=_collect_blocked_reasons(receipts_newest_first),
        merge_request_status=_merge_request_status(receipts_newest_first),
    )
