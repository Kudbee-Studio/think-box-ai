"""Live verification drill orchestration and attestation (never GitHub merge)."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_dashboard import (
    FounderGatedMergeService,
    PipelineDashboardAggregator,
    PipelineQuarantineController,
    compute_founder_merge_proof,
)
from thinkbox.pipeline_founder_telemetry import founder_proof_validation_event
from thinkbox.pipeline_live_staging import inspect_staging_config, resolve_org_memory_db_path
from thinkbox.pipeline_fleet_checkpoint import FleetCheckpointService, DEFAULT_FLEET_CHECKPOINT_KEY

FLEET_CHECKPOINT_VERSION = "fleet-checkpoint-v2"
LIVE_ATTESTATION_ACTION = "live_verification_attestation"


@dataclass
class LiveDrillEvidence:
    """Mutable drill journal (in-memory until persisted)."""

    correlation_id: str
    pr_number: int = 0
    webhook_delivery_ids: list[str] = field(default_factory=list)
    webhook_receipt_ids: list[str] = field(default_factory=list)
    founder_receipt_id: str = ""
    founder_telemetry: dict[str, Any] = field(default_factory=dict)
    merge_response: dict[str, Any] = field(default_factory=dict)
    adversarial_outcomes: list[dict[str, Any]] = field(default_factory=list)
    real_webhook_exercised: bool = False
    real_founder_merge_exercised: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "pr_number": self.pr_number,
            "webhook_delivery_ids": self.webhook_delivery_ids,
            "webhook_receipt_ids": self.webhook_receipt_ids,
            "founder_receipt_id": self.founder_receipt_id,
            "founder_telemetry": self.founder_telemetry,
            "merge_response": self.merge_response,
            "adversarial_outcomes": self.adversarial_outcomes,
            "real_webhook_exercised": self.real_webhook_exercised,
            "real_founder_merge_exercised": self.real_founder_merge_exercised,
        }


def new_correlation_id() -> str:
    return f"live_drill_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"


def preflight_report() -> dict[str, Any]:
    cfg = inspect_staging_config()
    cfg["correlation_id_hint"] = "assign at drill start via new_correlation_id()"
    cfg["github_merge"] = False
    cfg["merged"] = False
    return cfg


def record_webhook_delivery(
    store: OrgMemoryReceiptStore,
    *,
    delivery_id: str,
    correlation_id: str,
    pr_number: int,
    branch: str,
    event_type: str,
    signature_valid: bool,
    admission_allowed: bool,
) -> str:
    """Persist live webhook delivery receipt (no merge side effects)."""
    receipt = store.append_lifecycle(
        run_id=f"live_webhook_{correlation_id}",
        pr_number=pr_number,
        branch=branch,
        from_state="LIVE_DRILL",
        to_state="LIVE_DRILL",
        action="live_webhook_delivery",
        result="success" if signature_valid else "blocked",
        evidence_label="verified" if signature_valid and admission_allowed else "simulated",
        evidence={
            "delivery_id": delivery_id,
            "correlation_id": correlation_id,
            "event_type": event_type,
            "signature_valid": signature_valid,
            "admission_allowed": admission_allowed,
            "github_merge": False,
            "auto_merge": False,
        },
    )
    return receipt.receipt_id


def build_live_verification_attestation(
    store: OrgMemoryReceiptStore,
    evidence: LiveDrillEvidence,
    *,
    quarantine: dict[str, Any],
    fleet_checkpoint: Optional[dict[str, Any]],
    chain_verified: bool,
    staging_identity: str,
) -> dict[str, Any]:
    """Machine-readable attestation; LIVE_VERIFIED only with real drill flags + preflight."""
    pre = inspect_staging_config()
    head_rows = store.query(limit=1)
    chain_head = str(head_rows[0].get("entry_hash") or "GENESIS") if head_rows else "GENESIS"
    merge_resp = evidence.merge_response or {}
    github_merge_called = bool(merge_resp.get("github_merge_called"))
    merged = bool(merge_resp.get("merged"))
    live_ok = (
        pre.get("ready_for_live_drill")
        and evidence.real_webhook_exercised
        and evidence.real_founder_merge_exercised
        and chain_verified
        and not github_merge_called
        and not merged
        and not quarantine.get("quarantined")
    )
    attestation = {
        "schema": "LIVE_VERIFICATION_ATTESTATION",
        "pr_number": evidence.pr_number,
        "staging_environment_identity": staging_identity,
        "drill_correlation_id": evidence.correlation_id,
        "webhook_receipt_ids": evidence.webhook_receipt_ids,
        "webhook_delivery_ids": evidence.webhook_delivery_ids,
        "founder_admission_receipt_id": evidence.founder_receipt_id,
        "chain_head": chain_head,
        "chain_verification_result": chain_verified,
        "quarantine_state": quarantine,
        "github_merge_called": github_merge_called,
        "merged": merged,
        "fleet_checkpoint_identity": (fleet_checkpoint or {}).get("fleet_id"),
        "fleet_checkpoint_version": FLEET_CHECKPOINT_VERSION,
        "fleet_checkpoint": fleet_checkpoint,
        "timestamps": {
            "attested_at": datetime.now(timezone.utc).isoformat(),
        },
        "test_evidence": {
            "preflight_ready": pre.get("ready_for_live_drill"),
            "real_webhook_exercised": evidence.real_webhook_exercised,
            "real_founder_merge_exercised": evidence.real_founder_merge_exercised,
            "adversarial_outcomes": evidence.adversarial_outcomes,
        },
        "four_state": {
            "CODE_COMPLETE": True,
            "TEST_VERIFIED": True,
            "LIVE_VERIFIED": bool(live_ok),
            "PRODUCTION_READY": False,
        },
        "live_verified": bool(live_ok),
        "production_ready": False,
        "blockers": pre.get("missing_prerequisites") if not live_ok else [],
        "evidence_label": "verified" if live_ok else "simulated",
        "auto_merge": False,
    }
    attestation["attestation_digest"] = hashlib.sha256(
        json.dumps(attestation, sort_keys=True, default=str).encode()
    ).hexdigest()[:32]
    return attestation


def persist_live_attestation(store: OrgMemoryReceiptStore, attestation: dict[str, Any]) -> str:
    receipt = store.append_lifecycle(
        run_id=f"live_attest_{attestation.get('drill_correlation_id', 'unknown')}",
        pr_number=int(attestation.get("pr_number") or 0),
        branch="staging-live-drill",
        from_state="LIVE_DRILL",
        to_state="LIVE_DRILL",
        action=LIVE_ATTESTATION_ACTION,
        result="success" if attestation.get("live_verified") else "blocked",
        evidence_label=str(attestation.get("evidence_label") or "simulated"),
        evidence={**attestation, "github_merge": False},
    )
    return receipt.receipt_id


def run_live_drill_if_ready(
    *,
    merge_svc: FounderGatedMergeService,
    aggregator: PipelineDashboardAggregator,
    quarantine: PipelineQuarantineController,
    fleet: FleetCheckpointService,
    pr_number: int,
    governance_token: str,
    founder_proof: str,
    proof_key: str,
) -> dict[str, Any]:
    """Execute staging drill when preflight passes; otherwise fail-closed with blockers."""
    pre = preflight_report()
    if not pre.get("ready_for_live_drill"):
        return {
            "executed": False,
            "live_verified": False,
            "preflight": pre,
            "attestation": None,
            "github_merge_called": False,
            "merged": False,
        }

    store = aggregator._store  # noqa: SLF001
    corr = new_correlation_id()
    evidence = LiveDrillEvidence(correlation_id=corr, pr_number=pr_number)
    evidence.founder_telemetry = founder_proof_validation_event(
        pr_number, proof_key, founder_proof, correlation_id=corr
    )

    wrong_pr_proof = compute_founder_merge_proof(pr_number + 1, proof_key)
    wrong = merge_svc.request_merge(
        pr_number,
        governance_token=governance_token,
        founder_proof=wrong_pr_proof,
        quarantine_state=quarantine.read(),
    )
    evidence.adversarial_outcomes.append(
        {"attack": "wrong_pr_founder_proof", "detail": wrong.detail, "admitted": wrong.admitted}
    )

    q_armed = quarantine.read()
    if not q_armed.get("quarantined"):
        quarantine.set_quarantine(
            quarantined=True,
            reason="live_drill_adversarial",
            governance_token=governance_token,
        )
    denied_q = merge_svc.request_merge(
        pr_number,
        governance_token=governance_token,
        founder_proof=founder_proof,
        quarantine_state=quarantine.read(),
    )
    evidence.adversarial_outcomes.append(
        {"attack": "quarantine_armed", "detail": denied_q.detail, "admitted": denied_q.admitted}
    )
    quarantine.set_quarantine(
        quarantined=False,
        reason="live_drill_complete",
        governance_token=governance_token,
    )

    merge_result = merge_svc.request_merge(
        pr_number,
        governance_token=governance_token,
        founder_proof=founder_proof,
        idempotency_key=f"live-{corr}",
        quarantine_state=quarantine.read(),
    )
    evidence.real_founder_merge_exercised = merge_result.admitted and not merge_result.github_merge_called
    evidence.merge_response = merge_result.to_response_body()
    if merge_result.receipt_proof_hash:
        evidence.founder_receipt_id = merge_result.receipt_proof_hash

    dup = merge_svc.request_merge(
        pr_number,
        governance_token=governance_token,
        founder_proof=founder_proof,
        idempotency_key=f"live-{corr}",
        quarantine_state=quarantine.read(),
    )
    evidence.adversarial_outcomes.append(
        {"attack": "duplicate_request_merge", "detail": dup.detail, "idempotent": dup.idempotent}
    )

    evidence.real_webhook_exercised = False
    for row in store.query(pr_number=pr_number, limit=100):
        if str(row.get("action") or "") != "live_webhook_delivery":
            continue
        ev = row.get("evidence") or {}
        if str(ev.get("correlation_id") or "") == corr:
            evidence.real_webhook_exercised = True
            evidence.webhook_receipt_ids.append(str(row.get("receipt_id") or ""))
            did = str(ev.get("delivery_id") or "")
            if did:
                evidence.webhook_delivery_ids.append(did)

    cp = fleet.create_checkpoint(quarantine=quarantine.read())
    fleet_row = fleet.latest() or {}
    fleet_row["fleet_id"] = f"fleet-{corr}"
    fleet_row["checkpoint_version"] = FLEET_CHECKPOINT_VERSION

    att = build_live_verification_attestation(
        store,
        evidence,
        quarantine=quarantine.read(),
        fleet_checkpoint=fleet_row,
        chain_verified=store.verify(),
        staging_identity=pre.get("checks", {}).get("staging_environment_id") or "staging-unlabeled",
    )
    att["fleet_checkpoint_digest"] = cp.digest
    rid = persist_live_attestation(store, att)
    att["attestation_receipt_id"] = rid

    return {
        "executed": True,
        "live_verified": att.get("live_verified"),
        "preflight": pre,
        "attestation": att,
        "github_merge_called": False,
        "merged": False,
        "correlation_id": corr,
    }


def latest_live_attestation(store: OrgMemoryReceiptStore) -> Optional[dict[str, Any]]:
    for row in store.query(limit=30):
        if str(row.get("action") or "") == LIVE_ATTESTATION_ACTION:
            evidence = row.get("evidence") or {}
            return {
                "receipt_id": row.get("receipt_id"),
                "timestamp": row.get("timestamp"),
                "attestation": evidence,
                "entry_hash": row.get("entry_hash"),
            }
    return None
