"""Unit tests for PR #167 theme D swarm governance post166 deepen."""

from __future__ import annotations

import unittest

from thinkbox import kilo_swarm_governance_post166_deepen as swarm166
from thinkbox.swarm_governance_post166_deepen import (
    SWARM_GOV_POST166_LABEL,
    admission_evidence_shape_ok,
    swarm_governance_post166_contract_snippet,
)


class TestSwarmGovernancePost166Deepen(unittest.TestCase):
    def test_gate_constants(self) -> None:
        self.assertEqual(swarm166.GATE_ID, "swarm-governance-post166-deepen")
        self.assertEqual(swarm166.PR_NUMBER, 167)

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
        snippet = swarm_governance_post166_contract_snippet()
        self.assertEqual(snippet["label"], SWARM_GOV_POST166_LABEL)
        self.assertFalse(snippet["live_verified"])

    def test_hermetic_gate_closed(self) -> None:
        result = swarm166.hermetic_swarm_governance_post166_deepen_check(
            swarm166.minimal_swarm_governance_post166_deepen_environ(),
        )
        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
