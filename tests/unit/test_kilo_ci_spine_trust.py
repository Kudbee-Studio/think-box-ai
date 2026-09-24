"""Unit tests for PR #172 CI spine-trust gate module."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from thinkbox import kilo_pr172_ci_spine_trust as gate

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestCiSpineTrustGate(unittest.TestCase):
    def test_evaluate_passes_on_repo(self) -> None:
        result = gate.evaluate_ci_spine_trust(
            gate.CiSpineTrustMode.HERMETIC_UNIT,
            gate.minimal_ci_spine_trust_environ(),
        )
        self.assertTrue(result.ok, msg=result.violations)

    def test_invalid_fixture_rejected(self) -> None:
        path = REPO_ROOT / gate.FIXTURES_REL / "invalid_redundant_post_season.yml"
        ok, violations = gate.validate_pr172_ci_workflow_manifest(
            path.read_text(encoding="utf-8")
        )
        self.assertFalse(ok)
        codes = {v.code for v in violations}
        self.assertIn("ci_workflow_redundant_verify_script", codes)

    def test_checklist_document(self) -> None:
        doc = json.loads((REPO_ROOT / gate.CHECKLIST_REL).read_text(encoding="utf-8"))
        ok, violations = gate.validate_checklist_document(doc)
        self.assertTrue(ok, msg=violations)

    def test_fixture_suite(self) -> None:
        pos, neg, errors = gate.run_ci_spine_trust_fixture_suite()
        self.assertEqual(errors, [])
        self.assertGreaterEqual(pos, 1)
        self.assertGreaterEqual(neg, 1)

    def test_verify_operator_script(self) -> None:
        proc = subprocess.run(
            ["python3", str(gate.VERIFY_SCRIPT_REL)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
        body = json.loads(proc.stdout)
        self.assertFalse(body.get("live_verified", True))


if __name__ == "__main__":
    unittest.main()
