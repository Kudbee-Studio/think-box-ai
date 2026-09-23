"""Unit tests for thinkbox.cli_inspect (KUDBEECLI Phase 1 helpers)."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from thinkbox.cli_inspect import (
    discover_proof_files,
    ledger_verify_report,
    proof_check_report,
    redacted_environment_snapshot,
    resolve_ledger_path,
    swarm_agents_rollup,
    swarm_status_summary,
)
from thinkbox.ledger import ActionLedger
from thinkbox.swarm_stats import load_and_validate_proof

ROOT = Path(__file__).resolve().parents[2]
PROOF_SAMPLE = ROOT / "data/thinkboxmd/big_swarm_20260921_135330.json"


class TestLedgerResolve(unittest.TestCase):
    def test_resolve_explicit_missing_returns_none(self) -> None:
        self.assertIsNone(resolve_ledger_path("/nonexistent/ledger.db"))

    def test_resolve_env_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "custom.db"
            ActionLedger(path).append("a", "c", "act", True, "ok", {})
            with mock.patch.dict(os.environ, {"THINKBOX_LEDGER_PATH": str(path)}):
                self.assertEqual(resolve_ledger_path(), path)

    def test_ledger_verify_report_verbose(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.db"
            ledger = ActionLedger(path)
            ledger.append("agent", "goal:execute", "run", True, "allowed", {})
            ledger.append("agent", "goal:execute", "run", False, "denied", {})
            ledger.close()
            report = ledger_verify_report(path, verbose=True)
            self.assertTrue(report["valid"])
            self.assertEqual(report["entry_count"], 2)
            self.assertEqual(report["denied_count"], 1)


class TestProofCheck(unittest.TestCase):
    def test_proof_check_missing_file(self) -> None:
        report = proof_check_report(Path("/no/such/proof.json"))
        self.assertFalse(report["valid"])

    def test_proof_check_valid_sample(self) -> None:
        if not PROOF_SAMPLE.is_file():
            self.skipTest("sample proof missing")
        report = proof_check_report(PROOF_SAMPLE, metrics_only=True)
        self.assertTrue(report["valid"])
        self.assertIn("metrics", report)


class TestSwarmRollup(unittest.TestCase):
    def test_swarm_agents_on_sample(self) -> None:
        if not PROOF_SAMPLE.is_file():
            self.skipTest("sample proof missing")
        rollup = swarm_agents_rollup([PROOF_SAMPLE])
        self.assertEqual(rollup.proofs_considered, 1)
        self.assertGreater(rollup.total_worker_rows, 0)

    def test_swarm_status_empty_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = swarm_status_summary(discover_proof_files(Path(tmp), 3))
            self.assertEqual(summary["proofs_valid"], 0)


class TestEnvRedaction(unittest.TestCase):
    def test_secret_keys_redacted_in_snapshot(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"THINKBOX_API_TOKEN": "super-secret", "THINKBOX_FOO": "bar"},
            clear=False,
        ):
            snap = redacted_environment_snapshot()
            watched = snap["watched_env"]
            self.assertEqual(watched.get("THINKBOX_API_TOKEN"), "[REDACTED]")
            self.assertNotIn("super-secret", json.dumps(snap))


if __name__ == "__main__":
    unittest.main()
