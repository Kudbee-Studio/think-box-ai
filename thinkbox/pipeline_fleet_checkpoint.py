"""Fleet-wide checkpoint: bind ops scorecard to org-memory chain head."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore

DEFAULT_FLEET_CHECKPOINT_KEY = "hermetic-fleet-checkpoint-key"
CHECKPOINT_CAPABILITY = "pipeline:fleet:checkpoint"


@dataclass
class FleetCheckpoint:
    timestamp: str
    chain_head_hash: str
    scorecard: dict[str, Any]
    digest: str
    attestation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "chain_head_hash": self.chain_head_hash,
            "scorecard": self.scorecard,
            "digest": self.digest,
            "attestation": self.attestation,
            "evidence_label": "simulated",
            "auto_merge": False,
        }


def _chain_head_hash(store: OrgMemoryReceiptStore) -> str:
    rows = store.query(limit=1)
    return str(rows[0].get("entry_hash") or "GENESIS") if rows else "GENESIS"


def _sign_checkpoint(payload: dict[str, Any], key: str) -> str:
    body = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()
    return hmac.new(key.encode("utf-8"), body, hashlib.sha256).hexdigest()[:32]


class FleetCheckpointService:
    """Persist and verify fleet checkpoints in org-memory."""

    def __init__(
        self,
        store: OrgMemoryReceiptStore,
        aggregator: Any,
        *,
        attestation_key: str = DEFAULT_FLEET_CHECKPOINT_KEY,
    ) -> None:
        self._store = store
        self._aggregator = aggregator
        self._key = attestation_key

    def latest(self) -> Optional[dict[str, Any]]:
        for row in self._store.query(limit=40):
            if str(row.get("action") or "") != "pipeline_fleet_checkpoint":
                continue
            evidence = row.get("evidence") or {}
            return {
                "timestamp": row.get("timestamp"),
                "signed_timestamp": evidence.get("signed_timestamp"),
                "chain_head_hash": evidence.get("chain_head_hash"),
                "scorecard": evidence.get("scorecard"),
                "digest": evidence.get("digest"),
                "attestation": evidence.get("attestation"),
                "attestation_body": evidence.get("attestation_body"),
                "chain_verified": evidence.get("chain_verified"),
                "entry_hash": row.get("entry_hash"),
                "evidence_label": "simulated",
            }
        return None

    def create_checkpoint(self, *, quarantine: Optional[dict[str, Any]] = None) -> FleetCheckpoint:
        from thinkbox.pipeline_dashboard import pipeline_ops_scorecard

        overview = self._aggregator.overview()
        scorecard = pipeline_ops_scorecard(overview, quarantine=quarantine or {})
        head = _chain_head_hash(self._store)
        ts = datetime.now(timezone.utc).isoformat()
        core = {
            "timestamp": ts,
            "chain_head_hash": head,
            "scorecard": scorecard,
            "chain_verified": overview.get("chain_verified"),
        }
        digest = hashlib.sha256(
            json.dumps(core, sort_keys=True, default=str, separators=(",", ":")).encode()
        ).hexdigest()[:32]
        attestation = _sign_checkpoint({**core, "digest": digest}, self._key)
        attestation_body = json.dumps({**core, "digest": digest}, sort_keys=True, default=str, separators=(",", ":"))
        self._store.append_lifecycle(
            run_id="pipeline_fleet",
            pr_number=0,
            branch="control-plane",
            from_state="RUNNING",
            to_state="RUNNING",
            action="pipeline_fleet_checkpoint",
            result="success",
            evidence_label="simulated",
            evidence={
                "signed_timestamp": ts,
                "chain_head_hash": head,
                "scorecard": scorecard,
                "digest": digest,
                "attestation": attestation,
                "attestation_body": attestation_body,
                "chain_verified": overview.get("chain_verified"),
                "github_merge": False,
                "auto_merge": False,
                "fleet_id": os.environ.get("THINKBOX_FLEET_ID", "thinkbox-fleet-default"),
                "checkpoint_version": os.environ.get(
                    "THINKBOX_FLEET_CHECKPOINT_VERSION", "fleet-checkpoint-v2"
                ),
            },
        )
        return FleetCheckpoint(
            timestamp=ts,
            chain_head_hash=head,
            scorecard=scorecard,
            digest=digest,
            attestation=attestation,
        )

    def verify_latest(self) -> dict[str, Any]:
        row = self.latest()
        if not row:
            return {"verified": False, "reason": "no_checkpoint", "evidence_label": "simulated"}
        body = str(row.get("attestation_body") or "")
        if not body:
            return {"verified": False, "reason": "missing_attestation_body", "evidence_label": "simulated"}
        expected = hmac.new(self._key.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
        ok = hmac.compare_digest(str(row.get("attestation") or ""), expected)
        return {
            "verified": ok,
            "reason": "ok" if ok else "attestation_mismatch",
            "checkpoint": row,
            "evidence_label": "verified" if ok else "rejected",
        }
