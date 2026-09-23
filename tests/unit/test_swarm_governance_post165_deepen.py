"""Unit tests for PR #166 theme D swarm governance post165 deepen."""

from __future__ import annotations

import unittest

from thinkbox import kilo_swarm_governance_post165_deepen as deepen
from thinkbox.swarm_governance_post165_deepen import admission_evidence_shape_ok


class TestSwarmGovernancePost165Deepen(unittest.TestCase):
    def test_shape_rejects_live_verified(self) -> None:
        self.assertFalse(
            admission_evidence_shape_ok(
                {
                    "gate_id": "x",
                    "hermetic_operator_ok": True,
                    "live_verified": True,
                    "live_api_called": False,
                    "four_state_max": "TEST_VERIFIED",
                }
            )
        )

    def test_hermetic_gate(self) -> None:
        result = deepen.hermetic_swarm_governance_post165_deepen_check(
            deepen.minimal_swarm_governance_post165_deepen_environ(),
        )
        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
