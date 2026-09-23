"""Unit tests for live-smoke ↔ audit-flip correlation (PR #165 theme A)."""

from __future__ import annotations

import unittest

from thinkbox.kilo_live_smoke_evidence import audit_flip_candidate, minimal_valid_smoke_evidence_document
from thinkbox.live_smoke_audit_flip_correlation import (
    audit_flip_predicate_report,
    correlate_smoke_evidence_with_audit_pass,
    missing_flip_predicates,
)


class TestLiveSmokeAuditFlipCorrelation(unittest.TestCase):
    def test_hermetic_minimal_missing_predicates(self) -> None:
        doc = minimal_valid_smoke_evidence_document()
        missing = missing_flip_predicates(doc)
        self.assertIn("live_verified_not_true", missing)

    def test_flip_refused_includes_correlation(self) -> None:
        doc = minimal_valid_smoke_evidence_document()
        flip = audit_flip_candidate(doc, {"pr_number": 152, "gate_id": "live-smoke-evidence"})
        self.assertEqual(flip.get("audit_flip_status"), "refused")
        corr = flip.get("smoke_audit_correlation") or {}
        self.assertFalse(corr.get("can_flip"))
        self.assertIn("missing_predicates", corr)

    def test_predicate_report_all_false_for_hermetic(self) -> None:
        doc = minimal_valid_smoke_evidence_document()
        report = audit_flip_predicate_report(doc)
        self.assertFalse(report.can_flip)
        self.assertFalse(report.predicates.get("live_verified_true"))

    def test_correlate_honesty_flags(self) -> None:
        doc = minimal_valid_smoke_evidence_document()
        blob = correlate_smoke_evidence_with_audit_pass(doc, {"pr_number": 164})
        self.assertEqual(blob.get("four_state_max"), "TEST_VERIFIED")
        self.assertFalse(blob.get("live_verified"))


if __name__ == "__main__":
    unittest.main()
