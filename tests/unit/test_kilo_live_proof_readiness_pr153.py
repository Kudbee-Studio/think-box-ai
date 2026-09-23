"""Hermetic gates for PR #153 KILO live-smoke-operator (artifact write + audit flip CLI)."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from thinkbox import kilo_live_smoke_operator as op
from thinkbox.kilo_env_matrix import EnvMatrixMode
from thinkbox.kilo_live_proof_readiness import spine_contract_summary
from thinkbox.kilo_live_smoke_evidence import GATE_ID as SMOKE_GATE_ID

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestLiveSmokeOperatorGate(unittest.TestCase):
    def test_pr153_gate_id(self) -> None:
        self.assertEqual(op.GATE_ID, "live-smoke-operator")
        self.assertEqual(op.PR_NUMBER, 153)

    def test_hermetic_unit_passes(self) -> None:
        env = op.minimal_live_smoke_operator_environ()
        result = op.evaluate_live_smoke_operator(EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertTrue(result.ok, msg=result.violations)
        assert result.evidence is not None
        self.assertFalse(result.evidence.live_api_called)

    def test_requires_smoke_evidence_layer(self) -> None:
        env = op.minimal_live_smoke_operator_environ()
        with mock.patch(
            "thinkbox.kilo_live_smoke_operator.hermetic_live_smoke_evidence_operator_check",
            return_value=mock.Mock(ok=False),
        ):
            result = op.evaluate_live_smoke_operator(EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertFalse(result.ok)
        self.assertFalse(result.smoke_evidence_layer_ok)

    def test_spine_summary_includes_operator(self) -> None:
        summary = spine_contract_summary()
        block = summary.get("live_smoke_operator") or {}
        self.assertEqual(block.get("gate_id"), op.GATE_ID)
        self.assertTrue(block.get("hermetic_operator_ok"))
        self.assertEqual(summary.get("pr153_gate_id"), op.GATE_ID)

    def test_verify_script_exit_zero(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_live_smoke_operator.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

    def test_spine_verify_includes_operator(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_spine.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)


class TestBuildAndWrite(unittest.TestCase):
    def test_build_hermetic_defaults(self) -> None:
        doc, violations = op.build_hermetic_smoke_evidence()
        self.assertEqual(violations, [])
        self.assertFalse(doc["live_api_called"])

    def test_build_rejects_live_api_without_verified(self) -> None:
        _, violations = op.build_hermetic_smoke_evidence(
            live_api_called=True,
            live_verified=False,
        )
        codes = {v.code for v in violations}
        self.assertIn("live_api_without_verified", codes)

    def test_write_hermetic_roundtrip(self) -> None:
        doc, _ = op.build_hermetic_smoke_evidence(evidence_id="unittest_write")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "kilo_live_smoke_unittest.json"
            result = op.write_smoke_evidence_artifact(doc, path=path)
            self.assertTrue(result.ok, msg=result.violations)
            self.assertTrue(path.is_file())
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(loaded["evidence_artifact_path"])

    def test_write_refuses_secret_endpoint(self) -> None:
        doc, _ = op.build_hermetic_smoke_evidence()
        doc = dict(doc)
        doc["redacted_endpoints"] = {"box_url": "sk-abcdefghijklmnopqrstuvwxyz"}
        result = op.write_smoke_evidence_artifact(doc)
        self.assertFalse(result.ok)
        codes = {v.code for v in result.violations}
        self.assertTrue("secret_like_literal" in codes or "endpoint_not_redacted" in codes)

    def test_fixture_suite_counts(self) -> None:
        pos, neg, errors = op.run_operator_fixture_suite()
        self.assertEqual(errors, [])
        self.assertGreaterEqual(pos, 1)
        self.assertGreaterEqual(neg, 2)

    def test_default_artifact_path_pattern(self) -> None:
        path = op.default_artifact_path("test")
        self.assertIn("kilo_live_smoke_", path.name)


class TestAuditFlipCandidate(unittest.TestCase):
    def test_candidate_path_suffix(self) -> None:
        prior = REPO_ROOT / op.DEFAULT_AUDIT_PRIOR_REL
        out = op.audit_flip_candidate_path_for(prior)
        self.assertTrue(out.name.endswith(op.AUDIT_CANDIDATE_NAME_SUFFIX))

    def test_flip_refused_hermetic_write(self) -> None:
        doc, _ = op.build_hermetic_smoke_evidence(evidence_id="flip_refused")
        with tempfile.TemporaryDirectory() as tmp:
            art = Path(tmp) / "kilo_live_smoke_flip.json"
            write = op.write_smoke_evidence_artifact(doc, path=art)
            self.assertTrue(write.ok)
            cand_path, cand = op.write_audit_flip_candidate_file(
                write.document or doc,
                out_path=Path(tmp) / "candidate.json",
                artifact_exists=True,
            )
            self.assertEqual(cand["audit_flip_status"], "refused")
            self.assertFalse(cand["four_state"]["live_verified"])
            self.assertTrue(cand_path.is_file())

    def test_load_audit_prior(self) -> None:
        prior = op.load_audit_prior_pass()
        self.assertEqual(prior.get("pass_id"), "pr152")

    def test_parse_receipt_etag_mismatch(self) -> None:
        _, _, violations = op.parse_receipt_etag_pairs(["a"], [])
        codes = {v.code for v in violations}
        self.assertIn("etags_empty", codes)


class TestCli(unittest.TestCase):
    def test_cli_write_stdout(self) -> None:
        proc = subprocess.run(
            [
                "python3",
                "scripts/kilo_live_smoke_operator.py",
                "write",
                "--evidence-id",
                "cli_hermetic_test",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["ok"])
        path = REPO_ROOT / payload["path"]
        if path.is_file():
            path.unlink()

    def test_cli_validate_smoke_fixture_path(self) -> None:
        proc = subprocess.run(
            [
                "python3",
                "scripts/kilo_live_smoke_operator.py",
                "validate",
                "--path",
                "data/kilo_live_smoke_evidence/fixtures/valid_hermetic_minimal.json",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)

    def test_cli_summary(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/kilo_live_smoke_operator.py", "summary"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        self.assertEqual(data["gate_id"], op.GATE_ID)

    def test_verify_live_prep_fails_without_env(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_live_smoke_operator.py", "--live"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=op.minimal_live_smoke_operator_environ(),
        )
        self.assertEqual(proc.returncode, 1)


class TestHermeticHonesty(unittest.TestCase):
    def test_contract_summary_live_api_false(self) -> None:
        summary = op.live_smoke_operator_contract_summary()
        self.assertFalse(summary["live_api_called"])
        self.assertEqual(summary["four_state_max"], "TEST_VERIFIED")

    def test_gate_closed_default(self) -> None:
        self.assertTrue(op.live_smoke_operator_gate_closed())

    def test_required_prior_is_smoke_evidence(self) -> None:
        self.assertEqual(op.REQUIRED_PRIOR_GATE_IDS, frozenset({SMOKE_GATE_ID}))

    def test_pr152_layer_documented(self) -> None:
        summary = op.live_smoke_operator_contract_summary()
        self.assertEqual(summary["pr152_layer_gate_id"], SMOKE_GATE_ID)

    def test_redact_operator_summary(self) -> None:
        text = op.redact_operator_summary('{"x":"sk-abcdefghijklmnopqrstuvwxyz"}')
        self.assertIsInstance(text, str)

    def test_pr153_not_live_verified_on_disk(self) -> None:
        path = REPO_ROOT / "docs/audit/passes/2026-09-23-pr153.json"
        if path.is_file():
            doc = json.loads(path.read_text(encoding="utf-8"))
            self.assertFalse(doc["four_state"]["live_verified"])


if __name__ == "__main__":
    unittest.main()
