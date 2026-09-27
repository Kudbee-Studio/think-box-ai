"""Unit tests for PR #160 receipt-chain-end-link-docs gate."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from thinkbox import kilo_receipt_chain_end_link_docs as docs_gate
from thinkbox.kilo_env_matrix import EnvMatrixMode

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestReceiptChainEndLinkDocsGate(unittest.TestCase):
    def test_gate_constants(self) -> None:
        self.assertEqual(docs_gate.GATE_ID, "receipt-chain-end-link-docs")
        self.assertEqual(docs_gate.PR_NUMBER, 160)

    def test_era_pack_honesty(self) -> None:
        path = REPO_ROOT / docs_gate.ERA_CONSOLIDATED_REL
        body = json.loads(path.read_text(encoding="utf-8"))
        violations = docs_gate.validate_era_consolidated_pack(body)
        self.assertEqual(violations, [])

    def test_checklist_honesty(self) -> None:
        path = REPO_ROOT / docs_gate.CHECKLIST_REL
        body = json.loads(path.read_text(encoding="utf-8"))
        violations = docs_gate.validate_checklist_document(body)
        self.assertEqual(violations, [])

    def test_fixture_suite(self) -> None:
        pos, _neg, errors = docs_gate.run_docs_fixture_suite()
        self.assertFalse(errors, msg=errors)
        self.assertGreaterEqual(pos, 5)

    def test_evaluate_hermetic(self) -> None:
        env = docs_gate.minimal_receipt_chain_end_link_docs_environ()
        result = docs_gate.evaluate_receipt_chain_end_link_docs(EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertTrue(result.ok, msg=result.violations)


if __name__ == "__main__":
    unittest.main()
