"""Unit tests for thinkbox.swarm_stats (KILO swarm proof helpers)."""

import tempfile
import unittest
from pathlib import Path

from thinkbox.swarm_stats import (
    effective_rps,
    expected_live_calls,
    extract_convergence_metrics,
    load_and_validate_proof,
    latency_percentiles,
    open_action_ledger,
    summarize_convergence_proofs,
    summarize_metric_series,
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


def _synthetic_proof(
    *,
    run_id: str,
    rps: float,
    p50: float,
    ok: int,
    total: int,
    strength: float,
    reliability: float,
) -> dict:
    return {
        "run_id": run_id,
        "session_id": "s",
        "primary_workers": total - 32 if total >= 32 else total - 1,
        "validator_workers": min(32, total - 1),
        "workers": [{"role": "PRIMARY", "ok": True}] * ok
        + [{"role": "PRIMARY", "ok": False}] * (total - ok),
        "reconciliation": {
            "total_calls": total,
            "primary_calls": total - min(32, total - 1),
            "validator_calls": min(32, total - 1),
            "ok": ok,
            "failed": total - ok,
            "elapsed_s": round(total / rps, 2) if rps else 1.0,
            "effective_rps": rps,
            "p50_latency_s": p50,
            "traces": ok,
            "traces_grounded": ok,
            "strength": {
                "index": strength,
                "components": {"reliability": reliability},
            },
        },
    }


class TestConvergenceSummary(unittest.TestCase):
    def test_summarize_metric_series(self) -> None:
        stats = summarize_metric_series([10.0, 12.0, 14.0])
        self.assertEqual(stats["mean"], 12.0)
        self.assertEqual(stats["min"], 10.0)
        self.assertEqual(stats["max"], 14.0)
        self.assertEqual(stats["n"], 3)
        self.assertAlmostEqual(float(stats["stdev"]), 2.0, places=4)

    def test_single_run_stdev_zero(self) -> None:
        stats = summarize_metric_series([18.15])
        self.assertEqual(stats["stdev"], 0.0)

    def test_summarize_convergence_proofs(self) -> None:
        proofs = [
            _synthetic_proof(
                run_id="a",
                rps=18.0,
                p50=1.1,
                ok=256,
                total=256,
                strength=0.69,
                reliability=1.0,
            ),
            _synthetic_proof(
                run_id="b",
                rps=20.0,
                p50=1.0,
                ok=256,
                total=256,
                strength=0.70,
                reliability=1.0,
            ),
        ]
        agg = summarize_convergence_proofs(proofs)
        self.assertEqual(len(agg["runs"]), 2)
        rps = agg["summary"]["effective_rps"]
        self.assertEqual(rps["mean"], 19.0)
        self.assertEqual(rps["min"], 18.0)
        self.assertEqual(rps["max"], 20.0)

    def test_extract_convergence_metrics_ok_rate(self) -> None:
        proof = _synthetic_proof(
            run_id="c",
            rps=10.0,
            p50=2.0,
            ok=224,
            total=256,
            strength=0.65,
            reliability=0.875,
        )
        proof["primary_workers"] = 224
        proof["validator_workers"] = 32
        proof["workers"] = [{"role": "PRIMARY", "ok": True}] * 224 + [{"role": "VALIDATOR", "ok": True}] * 32
        proof["reconciliation"]["primary_calls"] = 224
        proof["reconciliation"]["validator_calls"] = 32
        proof["reconciliation"]["ok"] = 256
        proof["reconciliation"]["failed"] = 0
        m = extract_convergence_metrics(proof)
        self.assertEqual(m["ok_rate"], 1.0)
        self.assertEqual(m["strength_index"], 0.65)


if __name__ == "__main__":
    unittest.main()
