"""Unit tests for PR #169 theme D swarm governance post168 deepen."""

from __future__ import annotations

import unittest

from thinkbox import kilo_swarm_governance_post168_deepen as deepen
from thinkbox.swarm_governance_post168_deepen import (
    SWARM_GOV_POST168_LABEL,
    admission_evidence_shape_ok,
)


class TestSwarmGovernancePost168Deepen(unittest.TestCase):
    def test_gate_constants(self) -> None:
        self.assertEqual(deepen.GATE_ID, "swarm-governance-post168-deepen")
        self.assertEqual(deepen.PR_NUMBER, 169)

    def test_admission_shape_fail_closed(self) -> None:
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

    def test_hermetic_gate_closed(self) -> None:
        result = deepen.hermetic_swarm_governance_post168_deepen_check(
            deepen.minimal_swarm_governance_post168_deepen_environ(),
        )
        self.assertTrue(result.ok)
        self.assertEqual(SWARM_GOV_POST168_LABEL, "swarm-governance-post168-deepen")


if __name__ == "__main__":
    unittest.main()
