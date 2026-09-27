"""KILO gate tests for governance-evidence Live-proof readiness (PR #164)."""

from __future__ import annotations

import unittest

from thinkbox.kilo_governance_evidence_live_proof_readiness import (
    GATE_ID,
    PR_NUMBER,
    governance_evidence_live_proof_readiness_gate_closed,
    hermetic_governance_evidence_live_proof_readiness_check,
    minimal_governance_evidence_live_proof_readiness_environ,
)


class TestKiloGovernanceEvidenceLiveProofReadinessGate(unittest.TestCase):
    def test_gate_id(self) -> None:
        self.assertEqual(GATE_ID, "governance-evidence-live-proof-readiness")
        self.assertEqual(PR_NUMBER, 164)

    def test_hermetic_gate_closed(self) -> None:
        result = hermetic_governance_evidence_live_proof_readiness_check(
            minimal_governance_evidence_live_proof_readiness_environ()
        )
        self.assertTrue(result.ok, msg=[v.message for v in result.violations])

    def test_gate_closed_helper(self) -> None:
        self.assertTrue(governance_evidence_live_proof_readiness_gate_closed())


if __name__ == "__main__":
    unittest.main()
