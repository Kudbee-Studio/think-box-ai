"""Versioned merge-request policy — fail-closed after AdmissionGate."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from thinkbox.pipeline_readiness import MergeReadinessReport, evaluate_merge_readiness

from thinkbox.pipeline_dashboard import PipelineDashboardAggregator


@dataclass(frozen=True)
class PipelineMergePolicy:
    """Declarative gates applied before founder merge is queued."""

    version: str = "pipeline-merge-policy-v1"
    require_readiness_score: int = 100
    block_when_quarantine: bool = True
    block_when_chain_broken: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "require_readiness_score": self.require_readiness_score,
            "block_when_quarantine": self.block_when_quarantine,
            "block_when_chain_broken": self.block_when_chain_broken,
        }


DEFAULT_PIPELINE_MERGE_POLICY = PipelineMergePolicy()


@dataclass
class PolicyEvaluation:
    allowed: bool
    reason: str
    readiness: MergeReadinessReport
    policy: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "readiness": self.readiness.to_dict(),
            "policy": self.policy,
            "evidence_label": "simulated",
        }


def evaluate_merge_policy(
    aggregator: PipelineDashboardAggregator,
    pr_number: int,
    *,
    policy: PipelineMergePolicy | None = None,
) -> PolicyEvaluation:
    """Evaluate policy from org-memory; does not mutate store."""
    pol = policy or DEFAULT_PIPELINE_MERGE_POLICY
    store = aggregator._store  # noqa: SLF001
    readiness = evaluate_merge_readiness(store, pr_number)
    if pol.block_when_chain_broken and not store.verify():
        return PolicyEvaluation(
            allowed=False,
            reason="policy_chain_not_verified",
            readiness=readiness,
            policy=pol.to_dict(),
        )
    if pol.block_when_quarantine:
        quarantine_rows = store.query_by_action("pipeline_quarantine", limit=1)
        if quarantine_rows and (quarantine_rows[0].get("evidence") or {}).get("quarantined"):
            return PolicyEvaluation(
                allowed=False,
                reason="policy_quarantine_active",
                readiness=readiness,
                policy=pol.to_dict(),
            )
    if readiness.score < pol.require_readiness_score:
        return PolicyEvaluation(
            allowed=False,
            reason="policy_readiness_below_threshold",
            readiness=readiness,
            policy=pol.to_dict(),
        )
    return PolicyEvaluation(
        allowed=True,
        reason="policy_satisfied",
        readiness=readiness,
        policy=pol.to_dict(),
    )
