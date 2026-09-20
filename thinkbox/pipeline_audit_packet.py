"""Portable founder audit packets — offline-review bundle with HMAC attestation."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Optional

from thinkbox.pipeline_dashboard import PipelineDashboardAggregator
from thinkbox.pipeline_readiness import evaluate_merge_readiness

DEFAULT_AUDIT_ATTESTATION_KEY = "hermetic-pipeline-audit-key"


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()


def attest_audit_packet(body: dict[str, Any], attestation_key: str) -> str:
    """HMAC attestation over packet body (excludes attestation field)."""
    digest = hmac.new(attestation_key.encode("utf-8"), _canonical_json(body), hashlib.sha256).hexdigest()
    return digest[:32]


def build_founder_audit_packet(
    aggregator: PipelineDashboardAggregator,
    pr_number: int,
    *,
    attestation_key: str = DEFAULT_AUDIT_ATTESTATION_KEY,
    receipt_limit: int = 100,
) -> dict[str, Any]:
    """Assemble integrity, readiness, CI timeline, and receipt slice for founder review."""
    integrity = aggregator.verify_pr_receipt_integrity(pr_number, receipt_limit=receipt_limit)
    readiness = evaluate_merge_readiness(aggregator._store, pr_number, receipt_limit=receipt_limit)  # noqa: SLF001
    timeline = aggregator.ci_status_timeline(pr_number, receipt_limit=receipt_limit)
    detail = aggregator.pr_detail(pr_number, receipt_limit=min(receipt_limit, 50))
    body = {
        "pr_number": pr_number,
        "summary": detail.get("summary"),
        "integrity": integrity,
        "merge_readiness": readiness.to_dict(),
        "ci_timeline": timeline,
        "receipt_count": detail.get("receipt_count"),
        "receipts_preview": (detail.get("receipts") or [])[:12],
        "auto_merge": False,
        "github_merge": False,
        "evidence_label": "simulated",
    }
    body["packet_digest"] = hashlib.sha256(_canonical_json(body)).hexdigest()[:32]
    body["attestation"] = attest_audit_packet(body, attestation_key)
    return body
