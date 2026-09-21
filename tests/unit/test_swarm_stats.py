"""Unit tests for thinkbox.swarm_stats (KILO swarm proof helpers)."""

import math
import tempfile
import unittest
from pathlib import Path

from thinkbox.swarm_stats import (
    effective_rps,
    expected_live_calls,
    convergence_summary,
    load_and_validate_proof,
    latency_percentiles,
    open_action_ledger,
    proof_metrics,
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


class TestProofMetrics(unittest.TestCase):
    def test_metrics_returns_all_keys(self) -> None:
        if not PROOF_256.is_file():
            self.skipTest("proof artifact not present")
        payload, _ = load_and_validate_proof(PROOF_256)
        m = proof_metrics(payload)
        required = {
            "total_calls", "ok", "failed", "effective_rps", "elapsed_s",
            "p50_latency_s", "p95_latency_s", "max_latency_s",
            "traces_grounded", "ledger_entries_this_run",
            "primary_workers", "validator_workers",
        }
        self.assertEqual(set(m.keys()), required)

    def test_metrics_values_are_floats(self) -> None:
        if not PROOF_256.is_file():
            self.skipTest("proof artifact not present")
        payload, _ = load_and_validate_proof(PROOF_256)
        m = proof_metrics(payload)
        for k, v in m.items():
            self.assertIsInstance(v, float, f"{k} should be float")

    def test_metrics_ok_plus_failed_equals_total(self) -> None:
        if not PROOF_256.is_file():
            self.skipTest("proof artifact not present")
        payload, _ = load_and_validate_proof(PROOF_256)
        m = proof_metrics(payload)
        self.assertEqual(m["ok"] + m["failed"], m["total_calls"])

    def test_metrics_primary_plus_validator_equals_total(self) -> None:
        if not PROOF_256.is_file():
            self.skipTest("proof artifact not present")
        payload, _ = load_and_validate_proof(PROOF_256)
        m = proof_metrics(payload)
        self.assertEqual(m["primary_workers"] + m["validator_workers"], m["total_calls"])

    def test_metrics_traces_grounded_le_ok(self) -> None:
        if not PROOF_256.is_file():
            self.skipTest("proof artifact not present")
        payload, _ = load_and_validate_proof(PROOF_256)
        m = proof_metrics(payload)
        self.assertLessEqual(m["traces_grounded"], m["ok"])

    def test_metrics_non_negative(self) -> None:
        if not PROOF_256.is_file():
            self.skipTest("proof artifact not present")
        payload, _ = load_and_validate_proof(PROOF_256)
        m = proof_metrics(payload)
        for k, v in m.items():
            self.assertGreaterEqual(v, 0.0, f"{k} is negative")

    def test_metrics_match_reconciliation(self) -> None:
        if not PROOF_256.is_file():
            self.skipTest("proof artifact not present")
        payload, _ = load_and_validate_proof(PROOF_256)
        recon = payload["reconciliation"]
        m = proof_metrics(payload)
        self.assertEqual(m["total_calls"], float(recon["total_calls"]))
        self.assertEqual(m["effective_rps"], float(recon["effective_rps"]))
        self.assertEqual(m["elapsed_s"], float(recon["elapsed_s"]))

    def test_minimal_payload(self) -> None:
        payload = {
            "primary_workers": 2,
            "validator_workers": 1,
            "reconciliation": {
                "total_calls": 3, "ok": 2, "failed": 1,
                "effective_rps": 1.5, "elapsed_s": 2.0,
                "p50_latency_s": 0.5, "p95_latency_s": 1.0, "max_latency_s": 1.2,
                "traces_grounded": 2, "ledger_entries_this_run": 3,
            },
        }
        m = proof_metrics(payload)
        self.assertEqual(m["total_calls"], 3.0)
        self.assertEqual(m["ok"], 2.0)
        self.assertEqual(m["failed"], 1.0)
        self.assertEqual(m["primary_workers"], 2.0)
        self.assertEqual(m["validator_workers"], 1.0)


class TestConvergenceSummary(unittest.TestCase):
    def test_summary_has_required_keys(self) -> None:
        payloads = [
            {"total_calls": 256.0, "ok": 256.0, "failed": 0.0, "effective_rps": 24.52},
            {"total_calls": 256.0, "ok": 161.0, "failed": 95.0, "effective_rps": 38.79},
        ]
        s = convergence_summary(payloads)
        self.assertIn("n", s)
        self.assertIn("metrics", s)
        self.assertEqual(s["n"], 2)
        self.assertIn("total_calls", s["metrics"])
        self.assertIn("effective_rps", s["metrics"])

    def test_summary_n_matches_input_count(self) -> None:
        payloads = [{"total_calls": float(i)} for i in range(7)]
        s = convergence_summary(payloads)
        self.assertEqual(s["n"], 7)
        self.assertEqual(len(s["metrics"]["total_calls"]["values"]), 7)

    def test_summary_values_preserved(self) -> None:
        vals = [10.0, 20.0, 30.0, 40.0, 50.0]
        payloads = [{"total_calls": v} for v in vals]
        s = convergence_summary(payloads)
        self.assertEqual(s["metrics"]["total_calls"]["values"], vals)

    def test_summary_mean_is_correct(self) -> None:
        vals = [10.0, 20.0, 30.0]
        payloads = [{"total_calls": v} for v in vals]
        s = convergence_summary(payloads)
        stats = s["metrics"]["total_calls"]
        self.assertAlmostEqual(stats["mean"], 20.0, places=4)

    def test_summary_median_is_correct(self) -> None:
        vals = [10.0, 20.0, 30.0]
        payloads = [{"total_calls": v} for v in vals]
        s = convergence_summary(payloads)
        stats = s["metrics"]["total_calls"]
        self.assertAlmostEqual(stats["median"], 20.0, places=4)

    def test_summary_min_max(self) -> None:
        vals = [10.0, 20.0, 30.0]
        payloads = [{"total_calls": v} for v in vals]
        s = convergence_summary(payloads)
        stats = s["metrics"]["total_calls"]
        self.assertEqual(stats["min"], 10.0)
        self.assertEqual(stats["max"], 30.0)

    def test_summary_std_non_negative(self) -> None:
        vals = [10.0, 20.0, 30.0]
        payloads = [{"total_calls": v} for v in vals]
        s = convergence_summary(payloads)
        stats = s["metrics"]["total_calls"]
        self.assertGreaterEqual(stats["std"], 0.0)

    def test_summary_std_zero_for_identical(self) -> None:
        vals = [256.0] * 5
        payloads = [{"total_calls": v} for v in vals]
        s = convergence_summary(payloads)
        stats = s["metrics"]["total_calls"]
        self.assertAlmostEqual(stats["std"], 0.0, places=4)

    def test_summary_min_le_mean_le_max(self) -> None:
        vals = [15.0, 10.0, 25.0, 20.0, 5.0]
        payloads = [{"total_calls": v} for v in vals]
        s = convergence_summary(payloads)
        stats = s["metrics"]["total_calls"]
        self.assertLessEqual(stats["min"], stats["mean"])
        self.assertLessEqual(stats["mean"], stats["max"])

    def test_summary_values_are_rounded(self) -> None:
        vals = [1.111111, 2.222222, 3.333333]
        payloads = [{"effective_rps": v} for v in vals]
        s = convergence_summary(payloads)
        stats = s["metrics"]["effective_rps"]
        for v in stats["values"]:
            self.assertAlmostEqual(v, round(v, 4), places=4)

    def test_summary_includes_payloads(self) -> None:
        p1 = {"total_calls": 256.0, "ok": 256.0}
        p2 = {"total_calls": 200.0, "ok": 180.0}
        s = convergence_summary([p1, p2])
        self.assertEqual(len(s["payloads"]), 2)
        self.assertEqual(s["payloads"][0], p1)
        self.assertEqual(s["payloads"][1], p2)

    def test_summary_with_real_256_proofs(self) -> None:
        if not PROOF_256.is_file() or not PROOF_BASE.is_file():
            self.skipTest("proof artifacts not present")
        p256, _ = load_and_validate_proof(PROOF_256)
        pbase, _ = load_and_validate_proof(PROOF_BASE)
        s = convergence_summary([p256, pbase])
        self.assertEqual(s["n"], 2)
        self.assertEqual(s["metrics"]["total_calls"]["values"][0], 256.0)
        self.assertEqual(s["metrics"]["total_calls"]["values"][1], 132.0)
        self.assertGreaterEqual(s["metrics"]["effective_rps"]["mean"], 0.0)


if __name__ == "__main__":
    unittest.main()


class TestValidatorWaveConsistency(unittest.TestCase):
    def test_expected_live_calls_catches_skip(self) -> None:
        from thinkbox.swarm_stats import expected_live_calls
        self.assertEqual(expected_live_calls(224, 32), 256)
        with self.assertRaises(ValueError):
            expected_live_calls(0, 32)
        with self.assertRaises(ValueError):
            expected_live_calls(224, -1)

    def test_valid_proofs_have_complete_worker_counts(self) -> None:
        artifacts = [
            ROOT / "data/thinkboxmd/big_swarm_20260921_135330.json",
            ROOT / "data/thinkboxmd/big_swarm_20260921_152452.json",
            ROOT / "data/thinkboxmd/big_swarm_20260921_152726.json",
            ROOT / "data/thinkboxmd/big_swarm_20260921_152748.json",
            ROOT / "data/thinkboxmd/big_swarm_20260921_152836.json",
            ROOT / "data/thinkboxmd/big_swarm_20260921_152859.json",
            ROOT / "data/thinkboxmd/big_swarm_20260921_152948.json",
            ROOT / "data/thinkboxmd/big_swarm_20260921_171809.json",
            ROOT / "data/thinkboxmd/big_swarm_20260921_172241.json",
        ]
        for artifact in artifacts:
            if not artifact.is_file():
                self.skipTest(f"{artifact.name} not present")
            payload, errors = load_and_validate_proof(artifact)
            self.assertEqual(errors, [], f"{artifact.name} should validate: {errors}")
            recon = payload["reconciliation"]
            primary = recon.get("primary_calls", recon.get("primary_workers", 0))
            validator = recon.get("validator_calls", recon.get("validator_workers", 0))
            total = recon["total_calls"]
            self.assertEqual(primary + validator, total,
                             f"{artifact.name}: primary({primary})+validator({validator}) != total({total})")

    def test_validator_wave_skip_is_detected(self) -> None:
        artifact = ROOT / "data/thinkboxmd/big_swarm_20260921_172331.json"
        if not artifact.is_file():
            self.skipTest("validator wave skip artifact not present")
        payload, errors = load_and_validate_proof(artifact)
        self.assertTrue(len(errors) > 0, "Validator wave skip should be detected by proof validation")
        error_text = " ".join(errors).lower()
        self.assertTrue("total_calls" in error_text or "primary" in error_text,
                        f"Error should mention worker count mismatch: {errors}")


if __name__ == "__main__":
    unittest.main()
