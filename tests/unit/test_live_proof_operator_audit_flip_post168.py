"""Unit tests for PR #169 theme A operator audit-flip post168."""

from __future__ import annotations

import unittest

from thinkbox import kilo_live_proof_operator_audit_flip_post168 as audit_flip
from thinkbox.live_proof_operator_audit_flip_post168 import (
    OPERATOR_AUDIT_FLIP_POST168_LABEL,
    audit_flip_refused_post168_without_artifacts,
    operator_audit_flip_post168_checklist_items,
)


class TestLiveProofOperatorAuditFlipPost168(unittest.TestCase):
    def test_gate_constants(self) -> None:
        self.assertEqual(audit_flip.GATE_ID, "live-proof-operator-audit-flip-post168")
        self.assertEqual(audit_flip.PR_NUMBER, 169)

    def test_checklist_items_count(self) -> None:
        self.assertEqual(len(operator_audit_flip_post168_checklist_items()), 32)

    def test_audit_flip_refused_fail_closed(self) -> None:
        self.assertTrue(audit_flip_refused_post168_without_artifacts({}))

    def test_hermetic_gate_closed(self) -> None:
        result = audit_flip.hermetic_live_proof_operator_audit_flip_post168_check(
            audit_flip.minimal_live_proof_operator_audit_flip_post168_environ(),
        )
        self.assertTrue(result.ok)
        self.assertEqual(OPERATOR_AUDIT_FLIP_POST168_LABEL, "live-proof-operator-audit-flip-post168")


if __name__ == "__main__":
    unittest.main()
