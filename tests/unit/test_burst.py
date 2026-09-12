"""Unit tests for thinkbox/burst.py — THINK burst runner (offline)."""

import json
import tempfile
import unittest
from pathlib import Path

from thinkbox.admission import AdmissionGate
from thinkbox.burst import BurstBudget, BurstConfig, BurstRunner
from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.identity import IdentityLedger
from thinkbox.ledger import ActionLedger


def _config(tmp: str, **kwargs) -> BurstConfig:
    base = dict(max_pairs=3, output_dir=tmp)
    base.update(kwargs)
    return BurstConfig(**base)


def _read_records(path: str) -> list[dict]:
    text = Path(path).read_text().strip().splitlines()
    return [json.loads(line) for line in text]


class TestBurstBudget(unittest.TestCase):
    def test_charge_until_ceiling(self):
        budget = BurstBudget(max_calls=2, max_spend=1.0, cost_per_call=0.1)
        self.assertTrue(budget.charge())
        self.assertTrue(budget.charge())
        self.assertFalse(budget.charge())
        self.assertEqual(budget.calls, 2)

    def test_spend_ceiling(self):
        budget = BurstBudget(max_calls=100, max_spend=0.25, cost_per_call=0.1)
        self.assertTrue(budget.charge())
        self.assertTrue(budget.charge())
        self.assertFalse(budget.charge())
        self.assertLessEqual(budget.spend, 0.25)


class TestBurstRunnerOffline(unittest.TestCase):
    def test_offline_run_produces_pairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = BurstRunner(config=_config(tmp)).run()
            self.assertTrue(report.admitted)
            self.assertEqual(report.reason, "completed")
            self.assertEqual(report.pairs, 3)
            self.assertEqual(report.calls_used, 6)
            self.assertTrue(Path(report.output_path).exists())

    def test_jsonl_shape_and_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = BurstRunner(config=_config(tmp, max_pairs=1)).run()
            records = _read_records(report.output_path)
            self.assertEqual(len(records), 2)
            for record in records:
                for key in ("trace_id", "pair_id", "variant", "governance_token_id", "model", "grounded"):
                    self.assertIn(key, record)
            by_variant = {r["variant"]: r for r in records}
            self.assertIn("mesh", by_variant["grounded"]["tags"])
            self.assertIn("disruptor", by_variant["ungrounded"]["tags"])
            self.assertTrue(by_variant["grounded"]["grounded"])
            self.assertFalse(by_variant["ungrounded"]["grounded"])
            self.assertEqual(by_variant["grounded"]["governance_token_id"], "offline")

    def test_reasoning_captured(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = BurstRunner(config=_config(tmp, max_pairs=1)).run()
            self.assertEqual(report.reasoning_captured, 2)
            records = _read_records(report.output_path)
            self.assertTrue(all("reasoning" in r["metadata"] for r in records))

    def test_groundness_and_bind_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = BurstRunner(config=_config(tmp)).run()
            self.assertAlmostEqual(report.groundness_score, 0.5)
            self.assertEqual(report.bind_failure_rate, 1.0)

    def test_cash_budget_stops_early(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = BurstRunner(config=_config(tmp, max_calls=4)).run()
            self.assertEqual(report.pairs, 2)
            self.assertEqual(report.reason, "cash_budget_exhausted")

    def test_time_budget_stops_early(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = {"t": 0.0}

            def now() -> float:
                state["t"] += 1000.0
                return state["t"]

            report = BurstRunner(config=_config(tmp, max_minutes=1.0), now_fn=now).run()
            self.assertEqual(report.pairs, 0)
            self.assertEqual(report.reason, "time_budget_exhausted")

    def test_report_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            md = BurstRunner(config=_config(tmp)).run().to_markdown()
            self.assertIn("# THINK Burst Report", md)
            self.assertIn("Groundedness score", md)

    def test_ledger_records_admission_and_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ActionLedger(":memory:")
            report = BurstRunner(config=_config(tmp, max_pairs=2), ledger=ledger).run()
            self.assertTrue(report.ledger_valid)
            self.assertEqual(report.ledger_entries, report.calls_used + 1)
            self.assertTrue(ledger.verify())

    def test_evidence_text_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = BurstRunner(config=_config(tmp, max_pairs=1)).run()
            records = _read_records(report.output_path)
            grounded = next(r for r in records if r["variant"] == "grounded")
            ungrounded = next(r for r in records if r["variant"] == "ungrounded")
            self.assertIn("fact", grounded["evidence_text"])
            self.assertEqual(ungrounded["evidence_text"], "")


class TestBurstAdmission(unittest.TestCase):
    def _gate(self):
        tokens = GovernanceTokenService(signing_key="test-key")
        identities = IdentityLedger()
        identities.register(agent_id="kilo", capabilities=["goal:execute"])
        return tokens, identities, AdmissionGate(tokens, identities)

    def test_fails_closed_without_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, gate = self._gate()
            report = BurstRunner(config=_config(tmp), gate=gate, token_value="").run()
            self.assertFalse(report.admitted)
            self.assertEqual(report.reason, "token_invalid_or_expired")
            self.assertEqual(report.pairs, 0)

    def test_admitted_with_valid_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            tokens, _, gate = self._gate()
            token = tokens.issue(TokenRequest(agent_id="kilo", capabilities=["goal:execute"], ttl_seconds=60.0))
            report = BurstRunner(config=_config(tmp), gate=gate, token_value=token.token_value).run()
            self.assertTrue(report.admitted)
            self.assertEqual(report.governance_token_id, token.token_value[:24])


if __name__ == "__main__":
    unittest.main()