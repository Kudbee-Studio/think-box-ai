"""Unit tests for PR #168 theme D swarm governance post167 deepen."""

from __future__ import annotations

import unittest

from thinkbox import kilo_swarm_governance_post167_deepen as swarm167
from thinkbox.swarm_governance_post167_deepen import (
    SWARM_GOV_POST167_LABEL,
    admission_evidence_shape_ok,
    swarm_governance_post167_contract_snippet,
)


class TestSwarmGovernancePost167Deepen(unittest.TestCase):
    def test_gate_constants(self) -> None:
        self.assertEqual(swarm167.GATE_ID, "swarm-governance-post167-deepen")
        self.assertEqual(swarm167.PR_NUMBER, 168)

    def test_shape_fail_closed(self) -> None:
        self.assertFalse(admission_evidence_shape_ok({"live_verified": True}))
        self.assertTrue(
            admission_evidence_shape_ok(
                {
                    "gate_id": "x",
                    "hermetic_operator_ok": True,
                    "live_verified": False,
                    "live_api_called": False,
                    "four_state_max": "TEST_VERIFIED",
                },
            ),
        )

    def test_contract_snippet(self) -> None:
        snippet = swarm_governance_post167_contract_snippet()
        self.assertEqual(snippet["label"], SWARM_GOV_POST167_LABEL)
        self.assertFalse(snippet["live_verified"])

    def test_hermetic_gate_closed(self) -> None:
        result = swarm167.hermetic_swarm_governance_post167_deepen_check(
            swarm167.minimal_swarm_governance_post167_deepen_environ(),
        )
        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
