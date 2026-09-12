"""Unit tests for thinkbox/verifier.py — evaluation harness and reports."""

import tempfile
import unittest
from pathlib import Path

from thinkbox.disruptor import DisruptorResult
from thinkbox.verifier import Verifier, _verdict


def _result(name: str, category: str, passed: bool) -> DisruptorResult:
    return DisruptorResult(name=name, category=category, description="", outcome={}, passed=passed)


def _ctx() -> dict:
    from thinkbox.verifier import build_eval_fabric

    return build_eval_fabric()


class TestVerifier(unittest.TestCase):
    def test_full_pass_suite_verdict_strong(self):
        results = [
            _result("a", "token", True),
            _result("b", "capability", True),
            _result("c", "mesh", True),
            _result("d", "grounding", True),
            _result("e", "ledger", True),
            _result("f", "control", True),
            _result("g", "capacity", True),
        ]
        report = Verifier().evaluate(results, _ctx())
        self.assertEqual(report.metrics.pass_rate, 1.0)
        self.assertEqual(report.metrics.refusal_rate, 1.0)
        self.assertEqual(report.metrics.verdict, "STRONG")

    def test_partial_failure_lowers_score(self):
        results = [
            _result("a", "token", True),
            _result("b", "token", False),
            _result("c", "capability", True),
            _result("d", "mesh", False),
        ]
        report = Verifier().evaluate(results, _ctx())
        self.assertLess(report.metrics.overall_score, 1.0)
        self.assertLess(report.metrics.pass_rate, 1.0)
        self.assertIn(report.metrics.verdict, {"REVIEW", "FAIL", "PASS"})

    def test_empty_results_safe(self):
        report = Verifier().evaluate([], _ctx())
        self.assertEqual(report.metrics.passes_total, 0)
        self.assertEqual(report.metrics.pass_rate, 0.0)
        self.assertEqual(report.metrics.overall_score, 0.0)

    def test_markdown_renders_sections(self):
        report = Verifier().evaluate([_result("x", "token", True)], _ctx())
        md = report.to_markdown()
        self.assertIn("# Disruptor Evaluation Report", md)
        self.assertIn("## Pass results", md)
        self.assertIn("## Measured metrics", md)
        self.assertIn(report.metrics.verdict, md)

    def test_json_serializable(self):
        report = Verifier().evaluate([_result("x", "mesh", True)], _ctx())
        import json

        parsed = json.loads(report.to_json())
        self.assertEqual(parsed["metrics"]["verdict"], report.metrics.verdict)
        self.assertEqual(len(parsed["per_pass"]), 1)

    def test_to_dict_roundtrip(self):
        report = Verifier().evaluate([_result("x", "ledger", False)], _ctx())
        d = report.to_dict()
        self.assertEqual(d["metrics"]["tamper_detection"], 0.0)


class TestVerdict(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(_verdict(1.0), "STRONG")
        self.assertEqual(_verdict(0.92), "PASS")
        self.assertEqual(_verdict(0.80), "REVIEW")
        self.assertEqual(_verdict(0.40), "FAIL")


class TestEvalHarness(unittest.TestCase):
    def test_run_produces_full_suite(self):
        from thinkbox.verifier import EvalHarness

        harness = EvalHarness()
        report = harness.run()
        self.assertGreaterEqual(report.metrics.passes_total, 10)
        self.assertGreaterEqual(report.metrics.pass_rate, 0.9)

    def test_run_and_persist_writes_files(self):
        from thinkbox.verifier import EvalHarness

        with tempfile.TemporaryDirectory() as tmp:
            harness = EvalHarness()
            report = harness.run_and_persist(Path(tmp))
            files = list(Path(tmp).iterdir())
            self.assertEqual(len(files), 2)
            self.assertTrue(any(f.suffix == ".md" for f in files))
            self.assertTrue(any(f.suffix == ".json" for f in files))


if __name__ == "__main__":
    unittest.main()