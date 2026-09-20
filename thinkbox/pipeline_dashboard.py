"""Pipeline control surface: per-PR rollup from org-memory + founder-gated merge requests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from thinkbox.admission import AdmissionGate, AdmissionDecision
from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.identity import IdentityLedger
from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pr_lifecycle_event_hooks import PRLifecycleEventCoordinator

PIPELINE_FOUNDER_MERGE_CAPABILITY = "pipeline:founder:request_merge"
DEFAULT_FOUNDER_AGENT_ID = "pipeline-founder-gate"


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


class PipelineDashboardAggregator:
    """Read-only rollup of org-memory receipts per GitHub PR."""

    def __init__(self, store: OrgMemoryReceiptStore) -> None:
        self._store = store

    def list_summaries(self, *, receipt_limit_per_pr: int = 200) -> list[dict[str, Any]]:
        pr_numbers = self._store.distinct_pr_numbers()
        out: list[dict[str, Any]] = []
        for pr in pr_numbers:
            receipts = self._store.query(pr_number=pr, limit=receipt_limit_per_pr)
            out.append(summarize_pr_from_receipts(pr, receipts).to_dict())
        return out

    def pr_detail(self, pr_number: int, *, receipt_limit: int = 100) -> dict[str, Any]:
        receipts = self._store.query(pr_number=pr_number, limit=receipt_limit)
        summary = summarize_pr_from_receipts(pr_number, receipts)
        return {
            "summary": summary.to_dict(),
            "receipts": receipts,
            "receipt_count": len(receipts),
            "chain_verified": self._store.verify(),
            "evidence_label": "simulated",
            "auto_merge": False,
        }

    def overview(self) -> dict[str, Any]:
        summaries = self.list_summaries()
        totals = EvidenceLabelCounts()
        admission_total = 0
        for item in summaries:
            ec = item.get("evidence_counts") or {}
            totals.verified += int(ec.get("verified") or 0)
            totals.simulated += int(ec.get("simulated") or 0)
            totals.rejected += int(ec.get("rejected") or 0)
            admission_total += int(item.get("admission_denied_count") or 0)
        return {
            "pr_count": len(summaries),
            "prs": summaries,
            "totals": {
                "evidence_counts": totals.to_dict(),
                "admission_denied_count": admission_total,
            },
            "chain_verified": self._store.verify(),
            "evidence_label": "simulated",
            "auto_merge": False,
            "live_verified": False,
            "production_ready": False,
        }


@dataclass
class FounderMergeRequestResult:
    http_status: int
    admitted: bool
    merged: bool
    github_merge_called: bool
    evidence_label: str
    detail: str
    receipt_action: str = ""

    def to_response_body(self) -> dict[str, Any]:
        return {
            "admitted": self.admitted,
            "merged": self.merged,
            "github_merge_called": self.github_merge_called,
            "auto_merge": False,
            "evidence_label": self.evidence_label,
            "detail": self.detail,
            "receipt_action": self.receipt_action,
        }


class FounderGatedMergeService:
    """Admission-gated merge *request* — records org-memory only; never calls GitHub."""

    def __init__(
        self,
        store: OrgMemoryReceiptStore,
        gate: AdmissionGate,
        coordinator: PRLifecycleEventCoordinator,
        agent_id: str = DEFAULT_FOUNDER_AGENT_ID,
    ) -> None:
        self._store = store
        self._gate = gate
        self._coordinator = coordinator
        self._agent_id = agent_id

    def request_merge(
        self,
        pr_number: int,
        *,
        branch: str = "",
        governance_token: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> FounderMergeRequestResult:
        meta = dict(metadata or {})
        meta["pr_number"] = pr_number
        decision = self._gate.authorize(
            governance_token,
            self._agent_id,
            PIPELINE_FOUNDER_MERGE_CAPABILITY,
            metadata=meta,
        )
        if not decision.allowed:
            self._record_merge_denied(pr_number, branch, decision)
            return FounderMergeRequestResult(
                http_status=403,
                admitted=False,
                merged=False,
                github_merge_called=False,
                evidence_label="simulated",
                detail=decision.reason,
                receipt_action="merge_request_denied",
            )

        resolved_branch = branch or self._branch_for_pr(pr_number)
        self._store.append_lifecycle(
            run_id=self._run_id_for_pr(pr_number),
            pr_number=pr_number,
            branch=resolved_branch,
            from_state="READY_FOR_CLOSE",
            to_state="READY_FOR_CLOSE",
            action="founder_merge_requested",
            result="queued",
            evidence_label="verified",
            evidence={
                "github_merge": False,
                "auto_merge": False,
                "founder_gated": True,
                "agent_id": self._agent_id,
            },
        )
        return FounderMergeRequestResult(
            http_status=200,
            admitted=True,
            merged=False,
            github_merge_called=False,
            evidence_label="verified",
            detail="queued_for_founder_review",
            receipt_action="founder_merge_requested",
        )

    def _record_merge_denied(
        self,
        pr_number: int,
        branch: str,
        decision: AdmissionDecision,
    ) -> None:
        self._store.append_lifecycle(
            run_id=f"merge_denied_{pr_number}",
            pr_number=pr_number,
            branch=branch,
            from_state="BLOCKED",
            to_state="BLOCKED",
            action="merge_request_denied",
            result="blocked",
            evidence_label="simulated",
            evidence={
                "admission_reason": decision.reason,
                "capability": decision.capability,
                "agent_id": decision.agent_id,
                "github_merge": False,
            },
        )

    def _branch_for_pr(self, pr_number: int) -> str:
        rows = self._store.query(pr_number=pr_number, limit=1)
        if rows:
            return str(rows[0].get("branch") or "")
        return ""

    def _run_id_for_pr(self, pr_number: int) -> str:
        active = self._coordinator._runs_by_pr.get(pr_number)  # noqa: SLF001
        if active is not None:
            return active.run_id
        rows = self._store.query(pr_number=pr_number, limit=50)
        for row in rows:
            rid = str(row.get("run_id") or "")
            if rid and not rid.startswith("webhook_blocked_") and not rid.startswith("merge_denied_"):
                return rid
        return f"founder_merge_{pr_number}"


def build_hermetic_pipeline_dashboard(
    *,
    signing_key: str = "hermetic-pipeline-founder-key",
    agent_id: str = DEFAULT_FOUNDER_AGENT_ID,
) -> tuple[PipelineDashboardAggregator, FounderGatedMergeService, str]:
    """In-memory store, gate, and issued founder token (unit tests only)."""
    store = OrgMemoryReceiptStore(":memory:")
    coordinator = PRLifecycleEventCoordinator(store, test_mode=True)
    tokens = GovernanceTokenService(signing_key=signing_key)
    identities = IdentityLedger()
    identities.register(agent_id=agent_id, capabilities=[PIPELINE_FOUNDER_MERGE_CAPABILITY])
    issued = tokens.issue(
        TokenRequest(
            agent_id=agent_id,
            capabilities=[PIPELINE_FOUNDER_MERGE_CAPABILITY],
            ttl_seconds=3600.0,
        )
    )
    gate = AdmissionGate(tokens, identities)
    aggregator = PipelineDashboardAggregator(store)
    merge_svc = FounderGatedMergeService(store, gate, coordinator, agent_id=agent_id)
    return aggregator, merge_svc, issued.token_value
