"""Hermetic gates for PR #152 KILO live-smoke-evidence (bounded smoke binder)."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from thinkbox import kilo_live_smoke_evidence as smoke
from thinkbox.kilo_env_matrix import EnvMatrixMode
from thinkbox.kilo_live_proof_readiness import spine_contract_summary
from thinkbox.kilo_live_proof_exec import ARC_SEASON_COMPLETE
from thinkbox.kilo_post_season_harden import GATE_ID as POST_SEASON_GATE_ID
from thinkbox.kilo_substrate_checklist import BOX_URL_ENV

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestLiveSmokeEvidenceGate(unittest.TestCase):
    def test_pr152_gate_id(self) -> None:
        self.assertEqual(smoke.GATE_ID, "live-smoke-evidence")
        self.assertEqual(smoke.PR_NUMBER, 152)

    def test_hermetic_unit_passes(self) -> None:
        env = smoke.minimal_live_smoke_evidence_environ()
        result = smoke.evaluate_live_smoke_evidence(EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertTrue(result.ok, msg=result.violations)
        assert result.evidence is not None
        self.assertFalse(result.evidence.live_api_called)

    def test_requires_post_season_layer(self) -> None:
        env = smoke.minimal_live_smoke_evidence_environ()
        env = dict(env)
        env.pop("THINKBOX_KILO_MERCURY_MOCK", None)
        env.pop("THINKBOX_MERCURY_BASE_URL", None)
        env["INCEPTION_API_KEY"] = "sk-live-production-shaped-key"
        result = smoke.evaluate_live_smoke_evidence(EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertFalse(result.ok)
        self.assertFalse(result.post_season_harden_ok)

    def test_required_prior_includes_post_season(self) -> None:
        self.assertIn(POST_SEASON_GATE_ID, smoke.REQUIRED_PRIOR_GATE_IDS)
        self.assertIn("live-proof-exec", smoke.REQUIRED_PRIOR_GATE_IDS)

    def test_spine_summary_includes_live_smoke(self) -> None:
        summary = spine_contract_summary()
        block = summary.get("live_smoke_evidence") or {}
        self.assertEqual(block.get("gate_id"), smoke.GATE_ID)
        self.assertTrue(block.get("hermetic_operator_ok"))
        self.assertEqual(summary.get("pr152_gate_id"), smoke.GATE_ID)

    def test_verify_script_exit_zero(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_live_smoke_evidence.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)

    def test_spine_verify_includes_smoke(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_spine.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)


class TestSmokeEvidenceValidation(unittest.TestCase):
    def test_minimal_document_valid(self) -> None:
        doc = smoke.minimal_valid_smoke_evidence_document()
        self.assertTrue(smoke.validate_smoke_evidence_document(doc).ok)

    def test_valid_hermetic_fixture(self) -> None:
        doc = smoke.load_fixture("valid_hermetic_minimal.json")
        self.assertTrue(smoke.validate_smoke_evidence_document(doc).ok)

    def test_invalid_prior_gate_ids(self) -> None:
        doc = smoke.load_fixture("invalid_prior_gate_ids.json")
        codes = {v.code for v in smoke.validate_smoke_evidence_document(doc).violations}
        self.assertIn("prior_gate_ids_incomplete", codes)

    def test_invalid_missing_ack_marker(self) -> None:
        doc = smoke.load_fixture("invalid_missing_ack_marker.json")
        codes = {v.code for v in smoke.validate_smoke_evidence_document(doc).violations}
        self.assertIn("live_verified_without_evidence", codes)

    def test_invalid_missing_box_url(self) -> None:
        doc = smoke.load_fixture("invalid_missing_box_url.json")
        codes = {v.code for v in smoke.validate_smoke_evidence_document(doc).violations}
        self.assertIn("live_verified_without_evidence", codes)

    def test_invalid_forged_live_verified(self) -> None:
        doc = smoke.load_fixture("invalid_forged_live_verified.json")
        codes = {v.code for v in smoke.validate_smoke_evidence_document(doc).violations}
        self.assertIn("live_verified_without_evidence", codes)

    def test_invalid_secret_leakage(self) -> None:
        doc = smoke.load_fixture("invalid_secret_leakage.json")
        codes = {v.code for v in smoke.validate_smoke_evidence_document(doc).violations}
        self.assertTrue("secret_like_literal" in codes or "endpoint_not_redacted" in codes)

    def test_injected_cue_not_user_intent(self) -> None:
        doc = smoke.load_fixture("invalid_injected_cue.json")
        codes = {v.code for v in smoke.validate_smoke_evidence_document(doc).violations}
        self.assertIn("injected_cue_not_user_intent", codes)

    def test_fixture_suite_counts(self) -> None:
        pos, neg, errors = smoke.run_fixture_suite()
        self.assertEqual(errors, [])
        self.assertGreaterEqual(pos, 1)
        self.assertGreaterEqual(neg, 5)

    def test_season_marker_intact(self) -> None:
        doc = smoke.minimal_valid_smoke_evidence_document()
        self.assertEqual(doc["season_arc_marker"], ARC_SEASON_COMPLETE)


class TestAuditFlip(unittest.TestCase):
    def test_flip_refused_without_evidence(self) -> None:
        doc = smoke.minimal_valid_smoke_evidence_document()
        audit = {
            "pass_id": "pr151",
            "four_state": {"live_verified": False, "test_verified": True},
        }
        out = smoke.audit_flip_candidate(doc, audit, artifact_exists=False)
        self.assertEqual(out["audit_flip_status"], "refused")
        self.assertFalse(out["four_state"]["live_verified"])

    def test_can_flip_requires_all_predicates(self) -> None:
        doc = smoke.minimal_valid_smoke_evidence_document()
        self.assertFalse(smoke.can_flip_audit_live_verified(doc, artifact_exists=False))

    def test_can_flip_with_artifact_and_flags(self) -> None:
        doc = smoke.minimal_valid_smoke_evidence_document()
        doc = dict(doc)
        doc["live_verified"] = True
        doc["live_api_called"] = True
        doc["founder_ack_marker_present"] = True
        doc["box_url_present"] = True
        doc["evidence_artifact_path"] = "data/thinkboxmd/artifacts/kilo_live_smoke_test.json"
        self.assertTrue(smoke.can_flip_audit_live_verified(doc, artifact_exists=True))

    def test_flip_candidate_only_when_complete(self) -> None:
        doc = smoke.minimal_valid_smoke_evidence_document()
        doc = dict(doc)
        doc["live_verified"] = True
        doc["live_api_called"] = True
        doc["founder_ack_marker_present"] = True
        doc["box_url_present"] = True
        doc["evidence_artifact_path"] = "data/thinkboxmd/artifacts/kilo_live_smoke_test.json"
        audit = {"pass_id": "pr151", "four_state": {"live_verified": False}}
        out = smoke.audit_flip_candidate(doc, audit, artifact_exists=True)
        self.assertEqual(out["audit_flip_status"], "candidate_only")
        self.assertTrue(out["four_state"]["live_verified"])
        self.assertFalse(out["four_state"]["production_ready"])

    def test_founder_ack_env_canonical(self) -> None:
        doc = smoke.minimal_valid_smoke_evidence_document()
        self.assertEqual(doc["founder_ack_env_key"], smoke.FOUNDER_ACK_ENV)

    def test_box_url_env_canonical(self) -> None:
        doc = smoke.minimal_valid_smoke_evidence_document()
        self.assertEqual(doc["box_url_env_key"], BOX_URL_ENV)


class TestRedactionAndSchema(unittest.TestCase):
    def test_schema_gate_id(self) -> None:
        schema = smoke.smoke_evidence_json_schema()
        self.assertEqual(schema["gate_id"], smoke.GATE_ID)

    def test_redact_summary_no_crash(self) -> None:
        text = smoke.redact_smoke_evidence_summary('{"token":"sk-abcdefghijklmnopqrstuvwxyz"}')
        self.assertIsInstance(text, str)

    def test_gate_closed_default(self) -> None:
        self.assertTrue(smoke.live_smoke_evidence_gate_closed())

    def test_contract_summary_live_api_false(self) -> None:
        summary = smoke.live_smoke_evidence_contract_summary()
        self.assertFalse(summary["live_api_called"])
        self.assertEqual(summary["four_state_max"], "TEST_VERIFIED")

    def test_verify_live_prep_fails_without_env(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/verify_kilo_live_smoke_evidence.py", "--live"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=smoke.minimal_live_smoke_evidence_environ(),
        )
        self.assertEqual(proc.returncode, 1)

    def test_audit_pass_glob_documented(self) -> None:
        summary = smoke.live_smoke_evidence_contract_summary()
        self.assertIn("pr152", summary["audit_pass_glob"])


class TestHermeticHonesty(unittest.TestCase):
    def test_no_live_verified_in_minimal(self) -> None:
        doc = smoke.minimal_valid_smoke_evidence_document()
        self.assertFalse(doc["live_verified"])

    def test_ack_marker_false_by_default(self) -> None:
        doc = smoke.minimal_valid_smoke_evidence_document()
        self.assertFalse(doc[smoke.FOUNDER_ACK_MARKER_FIELD])

    def test_box_url_present_false_by_default(self) -> None:
        doc = smoke.minimal_valid_smoke_evidence_document()
        self.assertFalse(doc[smoke.BOX_URL_PRESENT_FIELD])

    def test_prior_gate_count(self) -> None:
        self.assertEqual(len(smoke.REQUIRED_PRIOR_GATE_IDS), 11)

    def test_pr152_audit_pass_on_disk_live_verified_false(self) -> None:
        path = REPO_ROOT / "docs/audit/passes/2026-09-23-pr152.json"
        if path.is_file():
            doc = json.loads(path.read_text(encoding="utf-8"))
            self.assertFalse(doc["four_state"]["live_verified"])


if __name__ == "__main__":
    unittest.main()
