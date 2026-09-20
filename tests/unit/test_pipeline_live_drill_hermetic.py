from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock

from thinkbox.admission import AdmissionGate
from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.identity import IdentityLedger
from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.github_webhook import DEFAULT_WEBHOOK_AGENT_ID, GITHUB_WEBHOOK_LIFECYCLE_CAPABILITY
from thinkbox.pipeline_dashboard import (
    DEFAULT_FOUNDER_AGENT_ID,
    PIPELINE_FLEET_CHECKPOINT_CAPABILITY,
    PIPELINE_FOUNDER_MERGE_CAPABILITY,
    FounderGatedMergeService,
    PipelineDashboardAggregator,
    PipelineQuarantineController,
    compute_founder_merge_proof,
)
from thinkbox.pipeline_fleet_checkpoint import FleetCheckpointService
from thinkbox.pipeline_live_drill import (
    exercise_staging_webhook_and_replay,
    latest_live_attestation,
    run_live_drill_if_ready,
)
from thinkbox.pipeline_live_staging import founder_proof_key_acceptable
from thinkbox.pipeline_waiver import PIPELINE_POLICY_WAIVER_CAPABILITY
from thinkbox.pr_lifecycle_event_hooks import PRLifecycleEventCoordinator

def _staging_env(db_path: str, *, physical: bool = False) -> dict[str, str]:
    signing = "staging-drill-signing-key"
    env = {
        "THINKBOX_PIPELINE_STAGING": "1",
        "THINKBOX_LIVE_DRILL_ENABLED": "1",
        "THINKBOX_ORG_MEMORY_DB": db_path,
        "THINKBOX_STAGING_ENVIRONMENT_ID": "staging-hermetic-cell",
        "WEBHOOK_SECRET": "whsec-staging-drill",
        "THINKBOX_FOUNDER_MERGE_PROOF_KEY": "operator-staging-proof-key-110",
        "THINKBOX_GITHUB_WEBHOOK_GOVERNANCE_TOKEN": "configured-for-preflight",
        "THINKBOX_GOVERNANCE_SIGNING_KEY": signing,
        "THINKBOX_PIPELINE_TEST_MODE": "false",
    }
    if physical:
        env["THINKBOX_LIVE_DRILL_PHYSICAL_STAGING"] = "1"
    return env


def _build_staging_bundle(db_path: str, proof_key: str):
    signing = os.environ["THINKBOX_GOVERNANCE_SIGNING_KEY"]
    store = OrgMemoryReceiptStore(db_path)
    coordinator = PRLifecycleEventCoordinator(store, test_mode=False)
    tokens = GovernanceTokenService(signing_key=signing)
    identities = IdentityLedger()
    caps = [
        PIPELINE_FOUNDER_MERGE_CAPABILITY,
        PipelineQuarantineController.QUARANTINE_CAPABILITY,
        PIPELINE_FLEET_CHECKPOINT_CAPABILITY,
        PIPELINE_POLICY_WAIVER_CAPABILITY,
    ]
    identities.register(agent_id=DEFAULT_FOUNDER_AGENT_ID, capabilities=caps)
    merge_token = tokens.issue(
        TokenRequest(agent_id=DEFAULT_FOUNDER_AGENT_ID, capabilities=caps, ttl_seconds=3600.0)
    ).token_value
    gate = AdmissionGate(tokens, identities)
    aggregator = PipelineDashboardAggregator(store)
    merge_svc = FounderGatedMergeService(
        store,
        gate,
        coordinator,
        agent_id=DEFAULT_FOUNDER_AGENT_ID,
        founder_proof_key=proof_key,
        aggregator=aggregator,
    )
    quarantine = PipelineQuarantineController(store, gate, agent_id=DEFAULT_FOUNDER_AGENT_ID)
    fleet = FleetCheckpointService(store, aggregator)
    return aggregator, merge_svc, quarantine, fleet, merge_token


class TestLiveDrillHermetic(unittest.TestCase):
    def test_milestone_webhook_replay_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "org_memory_staging.db")
            env = _staging_env(db, physical=False)
            with mock.patch.dict(os.environ, {k: v for k, v in env.items() if not k.startswith("_")}, clear=False):
                self.assertTrue(founder_proof_key_acceptable())
                store = OrgMemoryReceiptStore(db)
                wh = exercise_staging_webhook_and_replay(
                    store,
                    correlation_id="corr_hermetic_110",
                    pr_number=110,
                    db_path=db,
                )
                self.assertTrue(wh["webhook_verified"])
                self.assertTrue(wh["replay_rejected"])
                self.assertTrue(wh["replay_rejected_after_restart"])

    def test_drill_does_not_claim_live_verified_without_physical_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "org_memory_staging.db")
            env = _staging_env(db, physical=False)
            with mock.patch.dict(os.environ, {k: v for k, v in env.items() if not k.startswith("_")}, clear=False):
                proof_key = env["THINKBOX_FOUNDER_MERGE_PROOF_KEY"]
                bundle = _build_staging_bundle(db, proof_key)
                pr = 110
                proof = compute_founder_merge_proof(pr, proof_key)
                result = run_live_drill_if_ready(
                    merge_svc=bundle[1],
                    aggregator=bundle[0],
                    quarantine=bundle[2],
                    fleet=bundle[3],
                    pr_number=pr,
                    governance_token=bundle[4],
                    founder_proof=proof,
                    proof_key=proof_key,
                )
                self.assertTrue(result.get("executed"))
                self.assertFalse(result.get("live_verified"))
                att = result.get("attestation") or {}
                ms = att.get("verification_milestone") or {}
                self.assertFalse(ms.get("github_merge_called"))
                self.assertFalse(ms.get("merged"))
                self.assertTrue(ms.get("chain_verified"))
                self.assertTrue(ms.get("founder_proof_valid"))
                self.assertTrue(ms.get("webhook_verified"))
                self.assertTrue(ms.get("replay_rejected"))
                self.assertTrue(ms.get("quarantine_fail_closed"))
                latest = latest_live_attestation(bundle[0]._store)  # noqa: SLF001
                self.assertIsNotNone(latest)
                self.assertEqual(latest["attestation"].get("schema"), "LIVE_VERIFICATION_ATTESTATION")

    def test_physical_staging_reaches_live_verified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "org_memory_staging.db")
            env = _staging_env(db, physical=True)
            with mock.patch.dict(os.environ, {k: v for k, v in env.items() if not k.startswith("_")}, clear=False):
                proof_key = env["THINKBOX_FOUNDER_MERGE_PROOF_KEY"]
                bundle = _build_staging_bundle(db, proof_key)
                pr = 110
                proof = compute_founder_merge_proof(pr, proof_key)
                result = run_live_drill_if_ready(
                    merge_svc=bundle[1],
                    aggregator=bundle[0],
                    quarantine=bundle[2],
                    fleet=bundle[3],
                    pr_number=pr,
                    governance_token=bundle[4],
                    founder_proof=proof,
                    proof_key=proof_key,
                )
                self.assertTrue(result.get("live_verified"))
                att = result.get("attestation") or {}
                self.assertTrue(att.get("chain_verified"))
                self.assertTrue(att.get("live_verified"))


if __name__ == "__main__":
    unittest.main()
