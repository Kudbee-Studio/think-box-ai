"""Unit tests for PR #168 theme A operator audit-flip post167."""

from __future__ import annotations

import unittest

from thinkbox import kilo_live_proof_operator_audit_flip_post167 as audit_flip
from thinkbox.live_proof_operator_audit_flip_post167 import (
    OPERATOR_AUDIT_FLIP_POST167_LABEL,
    audit_flip_refused_post167_without_artifacts,
    operator_audit_flip_post167_checklist_items,
)


class TestLiveProofOperatorAuditFlipPost167(unittest.TestCase):
    def test_gate_constants(self) -> None:
        self.assertEqual(audit_flip.GATE_ID, "live-proof-operator-audit-flip-post167")
        self.assertEqual(audit_flip.PR_NUMBER, 168)

    def test_checklist_items_count(self) -> None:
        self.assertEqual(len(operator_audit_flip_post167_checklist_items()), 24)

    def test_audit_flip_refused_fail_closed(self) -> None:
        self.assertTrue(audit_flip_refused_post167_without_artifacts({}))

    def test_hermetic_gate_closed(self) -> None:
        result = audit_flip.hermetic_live_proof_operator_audit_flip_post167_check(
            audit_flip.minimal_live_proof_operator_audit_flip_post167_environ(),
        )
        self.assertTrue(result.ok)
        self.assertEqual(OPERATOR_AUDIT_FLIP_POST167_LABEL, "live-proof-operator-audit-flip-post167")


if __name__ == "__main__":
    unittest.main()
