"""Pipeline control surface: per-PR rollup from org-memory + founder-gated merge requests."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from thinkbox.admission import AdmissionGate, AdmissionDecision
from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.identity import IdentityLedger
from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_rollup import EvidenceLabelCounts, PRPipelineSummary, summarize_pr_from_receipts
from thinkbox.pr_lifecycle_event_hooks import PRLifecycleEventCoordinator

PIPELINE_FOUNDER_MERGE_CAPABILITY = "pipeline:founder:request_merge"
PIPELINE_FLEET_CHECKPOINT_CAPABILITY = "pipeline:fleet:checkpoint"
DEFAULT_FOUNDER_AGENT_ID = "pipeline-founder-gate"
DEFAULT_FOUNDER_PROOF_KEY = "hermetic-founder-merge-proof-key"


def compute_founder_merge_proof(pr_number: int, proof_key: str) -> str:
    """PR-bound HMAC proof (second factor alongside governance token)."""
    message = f"thinkbox:founder_merge:{int(pr_number)}".encode("utf-8")
    digest = hmac.new(proof_key.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return digest[:32]


def verify_founder_merge_proof(pr_number: int, proof_key: str, proof: str) -> bool:
    if not proof or not proof_key:
        return False
    expected = compute_founder_merge_proof(pr_number, proof_key)
    return hmac.compare_digest(expected, proof.strip())


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

    def admission_denial_ledger(
        self,
        *,
        since: Optional[str] = None,
        until: Optional[str] = None,
        receipt_limit: int = 500,
    ) -> dict[str, Any]:
        """Aggregate webhook/gate denial receipts by reason within a time window."""
        rows = self._store.query(since=since, until=until, limit=receipt_limit)
        by_reason: dict[str, int] = {}
        by_action: dict[str, int] = {}
        total = 0
        for row in rows:
            action = str(row.get("action") or "")
            if action not in ("admission_denied", "merge_request_denied"):
                continue
            total += 1
            by_action[action] = by_action.get(action, 0) + 1
            evidence = row.get("evidence") or {}
            reason = str(
                evidence.get("admission_reason")
                or evidence.get("reason")
                or action
            )
            by_reason[reason] = by_reason.get(reason, 0) + 1
        return {
            "since": since,
            "until": until,
            "total_denials": total,
            "by_reason": dict(sorted(by_reason.items(), key=lambda kv: (-kv[1], kv[0]))),
            "by_action": by_action,
            "receipt_limit": receipt_limit,
            "truncated": len(rows) >= receipt_limit,
            "evidence_label": "simulated",
            "auto_merge": False,
        }

    def verify_pr_receipt_integrity(self, pr_number: int, *, receipt_limit: int = 500) -> dict[str, Any]:
        """Hash-chain verify (global) plus per-PR receipt stats."""
        chain_ok = self._store.verify()
        rows = self._store.query(pr_number=pr_number, limit=receipt_limit)
        first_hash = rows[-1]["entry_hash"] if rows else ""
        last_hash = rows[0]["entry_hash"] if rows else ""
        return {
            "pr_number": pr_number,
            "receipt_count": len(rows),
            "chain_verified": chain_ok,
            "first_entry_hash": first_hash,
            "last_entry_hash": last_hash,
            "evidence_label": "verified" if chain_ok else "rejected",
            "auto_merge": False,
        }

    def ci_status_timeline(
        self,
        pr_number: int,
        *,
        receipt_limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Chronological CI observations from org-memory (oldest first)."""
        rows = self._store.query(pr_number=pr_number, limit=receipt_limit)
        events: list[dict[str, Any]] = []
        for row in reversed(rows):
            if str(row.get("action") or "") != "ci_status_observed":
                continue
            evidence = row.get("evidence") or {}
            events.append(
                {
                    "timestamp": row.get("timestamp"),
                    "workflow": evidence.get("workflow"),
                    "conclusion": evidence.get("conclusion"),
                    "ci_run_id": evidence.get("ci_run_id"),
                    "evidence_label": row.get("evidence_label"),
                    "entry_hash": row.get("entry_hash"),
                }
            )
        return events


@dataclass
class PipelineDeltaSnapshot:
    """Hermetic poll cursor for pipeline overview changes."""

    sequence: int
    pr_count: int
    admission_denied_total: int
    overview_digest: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "pr_count": self.pr_count,
            "admission_denied_total": self.admission_denied_total,
            "overview_digest": self.overview_digest,
            "evidence_label": "simulated",
        }


class PipelineDeltaTracker:
    """In-process snapshot diff for control-plane polling (no external SSE deps)."""

    def __init__(self, aggregator: PipelineDashboardAggregator) -> None:
        self._aggregator = aggregator
        self._last: Optional[PipelineDeltaSnapshot] = None
        self._sequence = 0

    def _digest_overview(self, overview: dict[str, Any]) -> str:
        body = json.dumps(
            {
                "pr_count": overview.get("pr_count"),
                "totals": overview.get("totals"),
                "prs": overview.get("prs"),
            },
            sort_keys=True,
            default=str,
        ).encode()
        return hashlib.sha256(body).hexdigest()[:16]

    def snapshot(self) -> dict[str, Any]:
        overview = self._aggregator.overview()
        admission_total = int((overview.get("totals") or {}).get("admission_denied_count") or 0)
        digest = self._digest_overview(overview)
        current = PipelineDeltaSnapshot(
            sequence=self._sequence,
            pr_count=int(overview.get("pr_count") or 0),
            admission_denied_total=admission_total,
            overview_digest=digest,
        )
        changed = self._last is None or self._last.overview_digest != current.overview_digest
        delta: dict[str, Any] = {
            "changed": changed,
            "current": current.to_dict(),
            "previous": self._last.to_dict() if self._last else None,
            "overview": overview if changed else None,
        }
        if changed:
            self._sequence += 1
            current = PipelineDeltaSnapshot(
                sequence=self._sequence,
                pr_count=current.pr_count,
                admission_denied_total=current.admission_denied_total,
                overview_digest=current.overview_digest,
            )
            self._last = current
            delta["current"] = current.to_dict()
        return delta


@dataclass
class PipelineQuarantineState:
    """Pipeline-scoped quarantine flag (org-memory backed receipt on toggle)."""

    quarantined: bool = False
    reason: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "quarantined": self.quarantined,
            "reason": self.reason,
            "updated_at": self.updated_at,
            "evidence_label": "simulated",
            "kill_switch_armed": self.quarantined,
        }


class PipelineQuarantineController:
    """Read/write quarantine with governance gate (never auto-merge)."""

    QUARANTINE_CAPABILITY = "pipeline:quarantine:mutate"

    def __init__(
        self,
        store: OrgMemoryReceiptStore,
        gate: AdmissionGate,
        agent_id: str = DEFAULT_FOUNDER_AGENT_ID,
    ) -> None:
        self._store = store
        self._gate = gate
        self._agent_id = agent_id
        self._state = PipelineQuarantineState()

    def read(self) -> dict[str, Any]:
        rows = self._store.query(limit=50)
        for row in rows:
            if str(row.get("action") or "") == "pipeline_quarantine":
                evidence = row.get("evidence") or {}
                self._state = PipelineQuarantineState(
                    quarantined=bool(evidence.get("quarantined")),
                    reason=str(evidence.get("reason") or ""),
                    updated_at=str(row.get("timestamp") or ""),
                )
                break
        return self._state.to_dict()

    def set_quarantine(
        self,
        *,
        quarantined: bool,
        reason: str,
        governance_token: str,
    ) -> dict[str, Any]:
        decision = self._gate.authorize(
            governance_token,
            self._agent_id,
            self.QUARANTINE_CAPABILITY,
            metadata={"quarantined": quarantined},
        )
        if not decision.allowed:
            return {
                "updated": False,
                "admitted": False,
                "detail": decision.reason,
                "evidence_label": "simulated",
                **self._state.to_dict(),
            }
        ts = datetime.now(timezone.utc).isoformat()
        self._store.append_lifecycle(
            run_id="pipeline_quarantine",
            pr_number=0,
            branch="control-plane",
            from_state="RUNNING",
            to_state="QUARANTINED" if quarantined else "RUNNING",
            action="pipeline_quarantine",
            result="success",
            evidence_label="simulated",
            evidence={
                "quarantined": quarantined,
                "reason": reason,
                "agent_id": self._agent_id,
                "github_merge": False,
                "auto_merge": False,
            },
        )
        self._state = PipelineQuarantineState(quarantined=quarantined, reason=reason, updated_at=ts)
        return {"updated": True, "admitted": True, "detail": "ok", **self._state.to_dict()}


def pipeline_ops_scorecard(overview: dict[str, Any], *, quarantine: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Raw autonomy/ops fields for dashboard API consumers."""
    q = quarantine or {}
    return {
        "autonomy_merge_enabled": False,
        "github_merge_enabled": False,
        "founder_gate_required": True,
        "admission_denied_total": int((overview.get("totals") or {}).get("admission_denied_count") or 0),
        "pr_count": int(overview.get("pr_count") or 0),
        "chain_verified": bool(overview.get("chain_verified")),
        "quarantine_active": bool(q.get("quarantined")),
        "live_verified": bool(overview.get("live_verified")),
        "production_ready": bool(overview.get("production_ready")),
        "evidence_label": "simulated",
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
    idempotent: bool = False
    deny_matrix: list[dict[str, Any]] = field(default_factory=list)
    receipt_proof_hash: str = ""

    def to_response_body(self) -> dict[str, Any]:
        return {
            "admitted": self.admitted,
            "merged": self.merged,
            "github_merge_called": self.github_merge_called,
            "auto_merge": False,
            "evidence_label": self.evidence_label,
            "detail": self.detail,
            "receipt_action": self.receipt_action,
            "idempotent": self.idempotent,
            "deny_matrix": self.deny_matrix,
            "receipt_proof_hash": self.receipt_proof_hash,
        }


class FounderGatedMergeService:
    """Admission-gated merge *request* — records org-memory only; never calls GitHub."""

    def __init__(
        self,
        store: OrgMemoryReceiptStore,
        gate: AdmissionGate,
        coordinator: PRLifecycleEventCoordinator,
        agent_id: str = DEFAULT_FOUNDER_AGENT_ID,
        founder_proof_key: str = DEFAULT_FOUNDER_PROOF_KEY,
        aggregator: Optional["PipelineDashboardAggregator"] = None,
        merge_policy: Optional[Any] = None,
    ) -> None:
        from thinkbox.pipeline_merge_policy import DEFAULT_PIPELINE_MERGE_POLICY

        self._store = store
        self._gate = gate
        self._coordinator = coordinator
        self._agent_id = agent_id
        self._founder_proof_key = founder_proof_key
        self._aggregator = aggregator
        self._merge_policy = merge_policy or DEFAULT_PIPELINE_MERGE_POLICY

    def request_merge(
        self,
        pr_number: int,
        *,
        branch: str = "",
        governance_token: str,
        founder_proof: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> FounderMergeRequestResult:
        meta = dict(metadata or {})
        meta["pr_number"] = pr_number
        deny_matrix: list[dict[str, Any]] = []

        proof_ok = verify_founder_merge_proof(pr_number, self._founder_proof_key, founder_proof)
        deny_matrix.append(
            {
                "check": "founder_merge_proof",
                "passed": proof_ok,
                "reason": "ok" if proof_ok else "founder_proof_invalid_or_missing",
            }
        )
        if not proof_ok:
            self._record_merge_denied(
                pr_number,
                branch,
                AdmissionDecision(False, "founder_proof_invalid_or_missing", self._agent_id, PIPELINE_FOUNDER_MERGE_CAPABILITY),
            )
            return FounderMergeRequestResult(
                http_status=403,
                admitted=False,
                merged=False,
                github_merge_called=False,
                evidence_label="simulated",
                detail="founder_proof_invalid_or_missing",
                receipt_action="merge_request_denied",
                deny_matrix=deny_matrix,
            )

        decision = self._gate.authorize(
            governance_token,
            self._agent_id,
            PIPELINE_FOUNDER_MERGE_CAPABILITY,
            metadata=meta,
        )
        deny_matrix.append(
            {
                "check": "admission_gate",
                "passed": decision.allowed,
                "reason": decision.reason,
                "capability": decision.capability,
            }
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
                deny_matrix=deny_matrix,
            )

        if self._aggregator is not None:
            from thinkbox.pipeline_merge_policy import evaluate_merge_policy

            pol = evaluate_merge_policy(self._aggregator, pr_number, policy=self._merge_policy)
            deny_matrix.append(
                {
                    "check": "merge_policy",
                    "passed": pol.allowed,
                    "reason": pol.reason,
                    "readiness_score": pol.readiness.score,
                }
            )
            if not pol.allowed:
                self._store.append_lifecycle(
                    run_id=f"merge_policy_{pr_number}",
                    pr_number=pr_number,
                    branch=branch,
                    from_state="BLOCKED",
                    to_state="BLOCKED",
                    action="merge_policy_denied",
                    result="blocked",
                    evidence_label="simulated",
                    evidence={
                        "policy_reason": pol.reason,
                        "readiness_score": pol.readiness.score,
                        "blockers": pol.readiness.blockers,
                        "github_merge": False,
                    },
                )
                return FounderMergeRequestResult(
                    http_status=403,
                    admitted=False,
                    merged=False,
                    github_merge_called=False,
                    evidence_label="simulated",
                    detail=pol.reason,
                    receipt_action="merge_policy_denied",
                    deny_matrix=deny_matrix,
                )

        if self._merge_already_queued(pr_number):
            return FounderMergeRequestResult(
                http_status=200,
                admitted=True,
                merged=False,
                github_merge_called=False,
                evidence_label="simulated",
                detail="already_queued",
                receipt_action="founder_merge_requested",
                idempotent=True,
                deny_matrix=deny_matrix,
                receipt_proof_hash=self._last_queue_proof_hash(pr_number),
            )

        resolved_branch = branch or self._branch_for_pr(pr_number)
        proof_hash = compute_founder_merge_proof(pr_number, self._founder_proof_key)
        receipt = self._store.append_lifecycle(
            run_id=self._run_id_for_pr(pr_number),
            pr_number=pr_number,
            branch=resolved_branch,
            from_state="READY_FOR_CLOSE",
            to_state="READY_FOR_CLOSE",
            action="founder_merge_requested",
            result="queued",
            evidence_label="simulated",
            evidence={
                "github_merge": False,
                "auto_merge": False,
                "founder_gated": True,
                "agent_id": self._agent_id,
                "founder_proof_hash": proof_hash,
                "admission_reason": decision.reason,
            },
        )
        return FounderMergeRequestResult(
            http_status=200,
            admitted=True,
            merged=False,
            github_merge_called=False,
            evidence_label="simulated",
            detail="queued_for_founder_review",
            receipt_action="founder_merge_requested",
            deny_matrix=deny_matrix,
            receipt_proof_hash=receipt.entry_hash,
        )

    def _merge_already_queued(self, pr_number: int) -> bool:
        rows = self._store.query(pr_number=pr_number, limit=30)
        for row in rows:
            if str(row.get("action") or "") == "founder_merge_requested" and row.get("result") == "queued":
                return True
            if str(row.get("action") or "") in ("merge_request_denied",):
                return False
        return False

    def _last_queue_proof_hash(self, pr_number: int) -> str:
        rows = self._store.query(pr_number=pr_number, limit=30)
        for row in rows:
            if str(row.get("action") or "") == "founder_merge_requested":
                return str(row.get("entry_hash") or "")
        return ""

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
    founder_proof_key: str = DEFAULT_FOUNDER_PROOF_KEY,
) -> tuple[PipelineDashboardAggregator, FounderGatedMergeService, str, str]:
    """In-memory store, gate, issued founder token, and PR proof (unit tests only)."""
    store = OrgMemoryReceiptStore(":memory:")
    coordinator = PRLifecycleEventCoordinator(store, test_mode=True)
    tokens = GovernanceTokenService(signing_key=signing_key)
    identities = IdentityLedger()
    identities.register(
        agent_id=agent_id,
        capabilities=[PIPELINE_FOUNDER_MERGE_CAPABILITY, PipelineQuarantineController.QUARANTINE_CAPABILITY, PIPELINE_FLEET_CHECKPOINT_CAPABILITY],
    )
    issued = tokens.issue(
        TokenRequest(
            agent_id=agent_id,
            capabilities=[
                PIPELINE_FOUNDER_MERGE_CAPABILITY,
                PipelineQuarantineController.QUARANTINE_CAPABILITY,
                PIPELINE_FLEET_CHECKPOINT_CAPABILITY,
            ],
            ttl_seconds=3600.0,
        )
    )
    gate = AdmissionGate(tokens, identities)
    aggregator = PipelineDashboardAggregator(store)
    merge_svc = FounderGatedMergeService(
        store,
        gate,
        coordinator,
        agent_id=agent_id,
        founder_proof_key=founder_proof_key,
        aggregator=aggregator,
    )
    return aggregator, merge_svc, issued.token_value, founder_proof_key


# Re-exports for tests and API consumers
from thinkbox.pipeline_rollup import EvidenceLabelCounts, PRPipelineSummary, summarize_pr_from_receipts  # noqa: E402,F401
