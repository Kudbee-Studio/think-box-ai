"""Unit tests for thinkbox/harvest.py — harvest replay."""

import json
import tempfile
import unittest
from pathlib import Path

from thinkbox.burst import BurstConfig, BurstRunner
from thinkbox.harvest import HarvestReplay


def _records() -> list[dict]:
    return [
        {
            "pair_id": "p1",
            "variant": "grounded",
            "thought": "Paris is the capital of France",
            "evidence_refs": ["fact_geo"],
            "evidence_text": "fact_geo: Paris is the capital of France",
            "metadata": {"reasoning": "direct lookup"},
        },
        {
            "pair_id": "p1",
            "variant": "ungrounded",
            "thought": "Paris is the capital of Italy",
            "evidence_refs": [],
            "evidence_text": "",
            "metadata": {"reasoning": "guess"},
        },
    ]


class TestHarvestReplay(unittest.TestCase):
    def test_analyze_pairs(self):
        report = HarvestReplay().analyze(_records())
        m = report.metrics
        self.assertEqual(m.records, 2)
        self.assertEqual(m.pairs, 1)
        self.assertEqual(m.grounded_variants, 1)
        self.assertEqual(m.ungrounded_variants, 1)
        self.assertEqual(m.reasoning_coverage, 1.0)
        self.assertGreater(m.groundedness_score, 0.7)
        self.assertEqual(m.bind_failure_rate, 1.0)

    def test_analyze_empty(self):
        report = HarvestReplay().analyze([])
        self.assertEqual(report.metrics.records, 0)
        self.assertEqual(report.metrics.pairs, 0)

    def test_records_without_pair_id_ignored(self):
        report = HarvestReplay().analyze([{"thought": "x"}])
        self.assertEqual(report.metrics.pairs, 0)

    def test_verify_runs_verifier_on_grounding_only(self):
        report = HarvestReplay().analyze(_records(), verify=True)
        self.assertIsNotNone(report.metrics.verifier_overall)
        self.assertGreaterEqual(report.metrics.verifier_overall, 0.9)
        self.assertEqual(report.metrics.verifier_verdict, "STRONG")

    def test_replay_dir_from_burst_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            BurstRunner(config=BurstConfig(max_pairs=2, output_dir=tmp)).run()
            report = HarvestReplay().replay_dir(tmp)
            self.assertEqual(report.metrics.pairs, 2)
            self.assertEqual(report.metrics.reasoning_coverage, 1.0)
            self.assertTrue(report.sources)

    def test_load_skips_malformed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.jsonl"
            path.write_text('{"pair_id":"p","variant":"grounded","thought":"a"}\nnot json\n')
            records = HarvestReplay().load([path])
            self.assertEqual(len(records), 1)

    def test_report_serialization(self):
        report = HarvestReplay().analyze(_records())
        parsed = json.loads(report.to_json())
        self.assertEqual(parsed["metrics"]["pairs"], 1)
        self.assertIn("Harvest Replay Report", report.to_markdown())


if __name__ == "__main__":
    unittest.main()