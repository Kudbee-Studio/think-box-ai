from __future__ import annotations

import unittest

from thinkbox.org_memory_receipts import OrgMemoryReceiptStore
from thinkbox.pipeline_live_drill import (
    LiveDrillEvidence,
    build_live_verification_attestation,
    preflight_report,
)


class TestLiveAttestation(unittest.TestCase):
    def test_cannot_claim_live_verified_without_prerequisites(self) -> None:
        store = OrgMemoryReceiptStore(":memory:")
        evidence = LiveDrillEvidence(correlation_id="corr_test", pr_number=110)
        evidence.real_webhook_exercised = True
        evidence.real_founder_merge_exercised = True
        att = build_live_verification_attestation(
            store,
            evidence,
            quarantine={"quarantined": False},
            fleet_checkpoint={"fleet_id": "f1"},
            chain_verified=True,
            staging_identity="test",
        )
        self.assertFalse(att["four_state"]["LIVE_VERIFIED"])
        self.assertFalse(att["live_verified"])
        self.assertFalse(att["github_merge_called"])
        self.assertFalse(att["merged"])

    def test_preflight_not_ready_in_cloud_agent(self) -> None:
        pre = preflight_report()
        self.assertFalse(pre.get("ready_for_live_drill"))


if __name__ == "__main__":
    unittest.main()
