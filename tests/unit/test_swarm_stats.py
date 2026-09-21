"""Unit tests for thinkbox.swarm_stats (KILO swarm proof helpers)."""

import tempfile
import unittest
from pathlib import Path

from thinkbox.swarm_stats import (
    effective_rps,
    expected_live_calls,
    load_and_validate_proof,
    latency_percentiles,
    open_action_ledger,
    validate_proof_document,
    validate_reconciliation,
)

ROOT = Path(__file__).resolve().parent.parent.parent
PROOF_256 = ROOT / "data/thinkboxmd/big_swarm_20260921_135330.json"
PROOF_BASE = ROOT / "data/thinkboxmd/big_swarm_20260921_135102.json"


class TestOpenActionLedger(unittest.TestCase):
    def test_fresh_ledger_clears_prior_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "action_ledger.db"
            ledger, _ = open_action_ledger(path, fresh=False)
            ledger.append("w1", "cap", "swarm", True, "admitted", {})
            self.assertEqual(len(ledger.entries(limit=10)), 1)
            fresh, at_start = open_action_ledger(path, fresh=True)
            self.assertEqual(at_start, 0)
            fresh.append("w2", "cap", "swarm", True, "admitted", {})
            self.assertEqual(len(fresh.entries(limit=10)), 1)


class TestSwarmStatsMath(unittest.TestCase):
    def test_effective_rps(self) -> None:
        self.assertEqual(effective_rps(100, 10.0), 10.0)
        if PROOF_256.is_file():
            payload, _ = load_and_validate_proof(PROOF_256)
            recon = payload["reconciliation"]
            self.assertLessEqual(
                abs(effective_rps(recon["total_calls"], recon["elapsed_s"]) - recon["effective_rps"]),
                0.02,
            )
        with self.assertRaises(ValueError):
            effective_rps(1, 0)

    def test_latency_percentiles_monotonic(self) -> None:
        stats = latency_percentiles([1.0, 2.0, 3.0, 4.0, 5.0])
        self.assertGreaterEqual(stats["p95_latency_s"], stats["p50_latency_s"])
        self.assertEqual(stats["max_latency_s"], 5.0)

    def test_expected_live_calls(self) -> None:
        self.assertEqual(expected_live_calls(224, 32), 256)


class TestSwarmProofArtifacts(unittest.TestCase):
    def test_scaled_proof_validates(self) -> None:
        if not PROOF_256.is_file():
            self.skipTest("proof artifact not present")
        payload, errors = load_and_validate_proof(PROOF_256)
        self.assertEqual(errors, [])
        self.assertEqual(payload["primary_workers"], 224)
        self.assertEqual(payload["validator_workers"], 32)
        recon = payload["reconciliation"]
        self.assertEqual(recon["total_calls"], 256)
        self.assertEqual(recon["ok"], 256)

    def test_baseline_proof_accounting(self) -> None:
        if not PROOF_BASE.is_file():
            self.skipTest("baseline proof not present")
        payload, errors = load_and_validate_proof(PROOF_BASE)
        self.assertEqual(errors, [])
        recon = payload["reconciliation"]
        self.assertEqual(recon["total_calls"], 132)
        self.assertEqual(recon["ok"], 112)
        self.assertEqual(recon["failed"], 20)


class TestValidateReconciliation(unittest.TestCase):
    def test_detects_rps_mismatch(self) -> None:
        workers = [{"role": "PRIMARY", "ok": True}] * 2
        recon = {
            "total_calls": 2,
            "primary_calls": 2,
            "validator_calls": 0,
            "ok": 2,
            "failed": 0,
            "elapsed_s": 10.0,
            "effective_rps": 99.0,
            "traces": 2,
            "traces_grounded": 2,
        }
        errs = validate_reconciliation(recon, workers)
        self.assertTrue(any("effective_rps" in e for e in errs))

    def test_validate_proof_document_minimal(self) -> None:
        payload = {
            "run_id": "x",
            "session_id": "s",
            "primary_workers": 2,
            "validator_workers": 1,
            "workers": [
                {"role": "PRIMARY", "ok": True},
                {"role": "PRIMARY", "ok": True},
                {"role": "VALIDATOR", "ok": True},
            ],
            "reconciliation": {
                "total_calls": 3,
                "primary_calls": 2,
                "validator_calls": 1,
                "ok": 3,
                "failed": 0,
                "elapsed_s": 3.0,
                "effective_rps": 1.0,
                "traces": 3,
                "traces_grounded": 3,
            },
        }
        self.assertEqual(validate_proof_document(payload), [])


if __name__ == "__main__":
    unittest.main()
