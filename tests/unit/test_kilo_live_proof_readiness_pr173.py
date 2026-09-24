"""Hermetic gates for PR #173 chronicle honesty (single-theme docs)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from thinkbox import kilo_pr173_chronicle_honesty as pr173

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestPr173ChronicleHonestyLane(unittest.TestCase):
    def test_pr173_gate_id(self) -> None:
        self.assertEqual(pr173.GATE_ID, "chronicle-honesty")
        self.assertEqual(pr173.PR_NUMBER, 173)

    def test_chronicle_documents_validate(self) -> None:
        ok, violations = pr173.validate_chronicle_documents()
        self.assertTrue(ok, msg=[(v.code, v.message) for v in violations])

    def test_pr173_not_combined_umbrella(self) -> None:
        summary = pr173.chronicle_honesty_contract_summary()
        self.assertFalse(summary.get("combined_umbrella_nested"))
        self.assertTrue(summary.get("hermetic_operator_ok"))

    def test_pr173_audit_pass_honesty(self) -> None:
        path = REPO_ROOT / pr173.PR173_PASS_REL
        body = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(body["live_verified"])
        self.assertFalse(body["live_api_called"])
        self.assertEqual(body["gate_id"], pr173.GATE_ID)


if __name__ == "__main__":
    unittest.main()
