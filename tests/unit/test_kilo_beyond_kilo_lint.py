"""Unit tests for beyond-KILO lint readiness gate (PR #170)."""

from __future__ import annotations

import json
import unittest

from thinkbox import kilo_beyond_kilo_lint as lint_gate
from thinkbox.kilo_hermetic_gate_memo import clear_hermetic_gate_memo
from thinkbox.kilo_live_proof_readiness import REPO_ROOT


class TestKiloBeyondKiloLintGate(unittest.TestCase):
    def setUp(self) -> None:
        clear_hermetic_gate_memo()

    def tearDown(self) -> None:
        clear_hermetic_gate_memo()

    def test_gate_id(self) -> None:
        self.assertEqual(lint_gate.GATE_ID, "beyond-kilo-lint-readiness")
        self.assertEqual(lint_gate.PR_NUMBER, 170)

    def test_minimal_environ_static_ok(self) -> None:
        result = lint_gate.hermetic_beyond_kilo_lint_check(
            lint_gate.minimal_beyond_kilo_lint_environ(),
        )
        self.assertTrue(result.ok)
        self.assertIsNotNone(result.evidence)
        self.assertFalse(result.evidence.lint_executed)

    def test_checklist_on_disk(self) -> None:
        path = REPO_ROOT / lint_gate.CHECKLIST_REL
        doc = json.loads(path.read_text(encoding="utf-8"))
        violations = lint_gate.validate_checklist_document(doc)
        self.assertEqual(violations, [])

    def test_contract_summary_honesty(self) -> None:
        summary = lint_gate.beyond_kilo_lint_contract_summary(
            lint_gate.minimal_beyond_kilo_lint_environ(),
        )
        self.assertTrue(summary.get("hermetic_operator_ok"))
        self.assertFalse(summary.get("live_verified", True))
        self.assertFalse(summary.get("live_api_called", True))
        self.assertFalse(summary.get("combined_umbrella_nested"))

    def test_not_nested_umbrella(self) -> None:
        summary = lint_gate.beyond_kilo_lint_contract_summary(
            lint_gate.minimal_beyond_kilo_lint_environ(),
        )
        self.assertEqual(len(summary.get("prior_gate_ids") or []), 1)


if __name__ == "__main__":
    unittest.main()
