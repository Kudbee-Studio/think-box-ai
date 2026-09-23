"""Unit tests for PR #166 theme A operator prep deepen."""

from __future__ import annotations

import unittest

from thinkbox import kilo_live_proof_operator_prep_deepen as prep
from thinkbox.live_proof_operator_prep_deepen import (
    OPERATOR_PREP_DEEPEN_LABEL,
    founder_credential_readiness,
    operator_prep_checklist_items,
    operator_prep_contract_snippet,
)


class TestLiveProofOperatorPrepDeepen(unittest.TestCase):
    def test_gate_constants(self) -> None:
        self.assertEqual(prep.GATE_ID, "live-proof-operator-prep-deepen")
        self.assertEqual(prep.PR_NUMBER, 166)

    def test_checklist_items_count(self) -> None:
        self.assertEqual(len(operator_prep_checklist_items()), 8)

    def test_founder_readiness_fail_closed(self) -> None:
        readiness = founder_credential_readiness({})
        self.assertFalse(readiness.ready_for_bounded_live_smoke)
        self.assertTrue(readiness.missing)

    def test_contract_snippet_honesty(self) -> None:
        snippet = operator_prep_contract_snippet()
        self.assertEqual(snippet["label"], OPERATOR_PREP_DEEPEN_LABEL)
        self.assertFalse(snippet["live_verified"])
        self.assertFalse(snippet["live_api_called"])

    def test_hermetic_gate_closed(self) -> None:
        result = prep.hermetic_live_proof_operator_prep_deepen_check(
            prep.minimal_live_proof_operator_prep_deepen_environ(),
        )
        self.assertTrue(result.ok)
        self.assertIsNotNone(result.evidence)


if __name__ == "__main__":
    unittest.main()
