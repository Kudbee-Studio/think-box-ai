"""Unit tests for PR #167 theme A operator audit-flip deepen."""

from __future__ import annotations

import unittest

from thinkbox import kilo_live_proof_operator_audit_flip_deepen as audit_flip
from thinkbox.live_proof_operator_audit_flip_deepen import (
    OPERATOR_AUDIT_FLIP_DEEPEN_LABEL,
    audit_flip_refused_without_artifacts,
    operator_audit_flip_checklist_items,
)


class TestLiveProofOperatorAuditFlipDeepen(unittest.TestCase):
    def test_gate_constants(self) -> None:
        self.assertEqual(audit_flip.GATE_ID, "live-proof-operator-audit-flip-deepen")
        self.assertEqual(audit_flip.PR_NUMBER, 167)

    def test_checklist_items_count(self) -> None:
        self.assertEqual(len(operator_audit_flip_checklist_items()), 16)

    def test_audit_flip_refused_fail_closed(self) -> None:
        self.assertTrue(audit_flip_refused_without_artifacts({}))

    def test_hermetic_gate_closed(self) -> None:
        result = audit_flip.hermetic_live_proof_operator_audit_flip_deepen_check(
            audit_flip.minimal_live_proof_operator_audit_flip_deepen_environ(),
        )
        self.assertTrue(result.ok)
        self.assertEqual(OPERATOR_AUDIT_FLIP_DEEPEN_LABEL, "live-proof-operator-audit-flip-deepen")


if __name__ == "__main__":
    unittest.main()
