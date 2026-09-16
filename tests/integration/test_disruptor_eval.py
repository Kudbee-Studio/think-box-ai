"""Integration test — KUDBEE disruptor evaluation harness.

Runs the full standard suite against a real control-fabric instance and
asserts the fabric holds under disruptor load (white paper §11):
  - admission tests fail closed
  - compromised cell containment
  - tamper evidence
  - contrast pairs
  - elastic occupancy
"""

import tempfile
import unittest
from pathlib import Path

from thinkbox.verifier import EvalHarness


class TestDisruptorEvaluationE2E(unittest.TestCase):
    def test_fabric_holds_under_disruptor_load(self):
        harness = EvalHarness()
        report = harness.run()
        metrics = report.metrics

        self.assertGreaterEqual(metrics.passes_total, 15)
        self.assertGreaterEqual(metrics.pass_rate, 0.9)
        self.assertGreaterEqual(metrics.refusal_rate, 0.9)
        self.assertGreaterEqual(metrics.containment_rate, 1.0)
        self.assertGreaterEqual(metrics.grounding_accuracy, 1.0)
        self.assertGreaterEqual(metrics.tamper_detection, 1.0)
        self.assertGreaterEqual(metrics.admission_recall, 1.0)
        self.assertIn(metrics.verdict, {"STRONG", "PASS"})

    def test_expanded_passes_present(self):
        harness = EvalHarness()
        report = harness.run()
        names = {row["name"] for row in report.per_pass}
        for expected in (
            "cross_tenant_isolation",
            "reasoning_grounding",
            "replay_after_revocation",
            "cell_hopping",
            "ledger_tamper_detected",
        ):
            self.assertIn(expected, names)

    def test_report_persists_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            harness = EvalHarness()
            report = harness.run_and_persist(Path(tmp))
            files = list(Path(tmp).iterdir())
            self.assertEqual(len(files), 2)
            md = [f for f in files if f.suffix == ".md"][0]
            text = md.read_text()
            self.assertIn("# Disruptor Evaluation Report", text)
            self.assertIn(report.metrics.verdict, text)

    def test_fabric_state_reflects_scenarios(self):
        harness = EvalHarness()
        report = harness.run()
        cells = harness.fabric["cells"]
        self.assertTrue(cells["beta"].compromised)
        self.assertFalse(cells["core"].compromised)
        self.assertEqual(len(harness.fabric["ledger"].entries()), 2)


if __name__ == "__main__":
    unittest.main()