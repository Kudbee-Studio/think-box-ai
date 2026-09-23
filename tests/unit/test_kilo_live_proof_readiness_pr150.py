"""Hermetic gates for PR #150 KILO live-proof-exec (gate ``live-proof-exec``)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from thinkbox import kilo_live_proof_exec as live_exec
from thinkbox import kilo_live_proof_readiness as spine
from thinkbox.kilo_env_matrix import EnvMatrixMode
from thinkbox.kilo_substrate_checklist import BOX_URL_ENV

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestLiveProofExecGate(unittest.TestCase):
    def test_pr150_gate_id(self) -> None:
        gate = spine.gate_for_pr(150)
        self.assertIsNotNone(gate)
        assert gate is not None
        self.assertEqual(gate.gate_id, live_exec.GATE_ID)
        self.assertEqual(live_exec.PR_NUMBER, 150)

    def test_arc_includes_live_proof_exec(self) -> None:
        self.assertIn("live-proof-exec", spine.gate_ids())

    def test_required_prior_gates_complete(self) -> None:
        expected = {g.gate_id for g in spine.ARC_GATES if g.pr_number < 150}
        self.assertEqual(live_exec.REQUIRED_PRIOR_GATE_IDS, expected)

    def test_hermetic_unit_passes_clean_env(self) -> None:
        env = live_exec.minimal_live_proof_exec_environ()
        result = live_exec.evaluate_live_proof_exec(EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertTrue(result.ok, msg=result.violations)
        self.assertTrue(result.dashboard_slots_ok)
        assert result.evidence is not None
        self.assertFalse(result.evidence.live_api_called)

    def test_requires_dashboard_slots_layer(self) -> None:
        env = live_exec.minimal_live_proof_exec_environ()
        env = dict(env)
        env.pop("THINKBOX_KILO_MERCURY_MOCK", None)
        env.pop("THINKBOX_MERCURY_BASE_URL", None)
        env["INCEPTION_API_KEY"] = "sk-live-production-shaped-key"
        result = live_exec.evaluate_live_proof_exec(EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertFalse(result.ok)
        self.assertFalse(result.dashboard_slots_ok)

    def test_founder_ack_env_canonical(self) -> None:
        self.assertEqual(live_exec.FOUNDER_ACK_ENV, "THINKBOX_SWARM_LIVE_ACK")

    def test_box_url_env_canonical(self) -> None:
        doc = live_exec.minimal_valid_execution_plan_document()
        self.assertEqual(doc["box_url_env_key"], BOX_URL_ENV)


class TestExecutionPlanValidation(unittest.TestCase):
    def test_minimal_plan_valid(self) -> None:
        doc = live_exec.minimal_valid_execution_plan_document()
        result = live_exec.validate_execution_plan_document(doc)
        self.assertTrue(result.ok, msg=result.violations)

    def test_valid_minimal_fixture(self) -> None:
        doc = live_exec.load_fixture("valid_minimal.json")
        self.assertTrue(live_exec.validate_execution_plan_document(doc).ok)

    def test_invalid_prior_gate_ids(self) -> None:
        doc = live_exec.load_fixture("invalid_prior_gate_ids.json")
        codes = {v.code for v in live_exec.validate_execution_plan_document(doc).violations}
        self.assertIn("prior_gate_ids_incomplete", codes)

    def test_invalid_live_verified(self) -> None:
        doc = live_exec.load_fixture("invalid_live_verified.json")
        codes = {v.code for v in live_exec.validate_execution_plan_document(doc).violations}
        self.assertTrue(
            "live_verified_forbidden" in codes or "four_state_cap_exceeded" in codes
        )

    def test_invalid_live_api_called(self) -> None:
        doc = live_exec.load_fixture("invalid_live_api_called.json")
        codes = {v.code for v in live_exec.validate_execution_plan_document(doc).violations}
        self.assertIn("live_api_forbidden", codes)

    def test_invalid_founder_ack_key(self) -> None:
        doc = live_exec.load_fixture("invalid_founder_ack_key.json")
        codes = {v.code for v in live_exec.validate_execution_plan_document(doc).violations}
        self.assertIn("founder_ack_env_key", codes)

    def test_invalid_season_marker(self) -> None:
        doc = live_exec.load_fixture("invalid_season_marker.json")
        codes = {v.code for v in live_exec.validate_execution_plan_document(doc).violations}
        self.assertIn("season_arc_marker", codes)

    def test_cannot_claim_live_without_artifact_file(self) -> None:
        doc = live_exec.minimal_valid_execution_plan_document()
        doc = dict(doc)
        doc["live_verified"] = True
        doc["evidence_artifact_path"] = "data/thinkboxmd/artifacts/does_not_exist_pr150.json"
        self.assertFalse(live_exec.can_claim_live_verified(doc, artifact_exists=False))

    def test_halt_reasons_from_proof_schema(self) -> None:
        doc = live_exec.minimal_valid_execution_plan_document()
        for reason in doc["halt_reasons_allowed"]:
            self.assertIn(reason, live_exec.execution_plan_json_schema()["halt_reasons"])


class TestLiveEnvReadiness(unittest.TestCase):
    def test_live_exec_env_closed_without_ack(self) -> None:
        env = live_exec.minimal_live_proof_exec_environ()
        self.assertFalse(live_exec.live_exec_env_ready(env))

    def test_live_exec_env_ready_with_ack_and_url(self) -> None:
        env = live_exec.minimal_live_proof_exec_environ(
            {
                live_exec.FOUNDER_ACK_ENV: "1",
                BOX_URL_ENV: "https://example-3000.preview.box.upstash.com",
            }
        )
        self.assertTrue(live_exec.live_exec_env_ready(env))

    def test_hermetic_mode_rejects_live_env_ready(self) -> None:
        env = live_exec.minimal_live_proof_exec_environ(
            {
                live_exec.FOUNDER_ACK_ENV: "1",
                BOX_URL_ENV: "https://example-3000.preview.box.upstash.com",
            }
        )
        result = live_exec.evaluate_live_proof_exec(EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertFalse(result.ok)
        codes = {v.code for v in result.violations}
        self.assertIn("live_env_in_hermetic_mode", codes)


class TestSpineAndOperators(unittest.TestCase):
    def test_spine_includes_live_proof_exec_block(self) -> None:
        summary = spine.spine_contract_summary()
        self.assertEqual(summary.get("pr150_gate_id"), live_exec.GATE_ID)
        self.assertTrue(summary.get("arc_season_complete"))
        block = summary.get("live_proof_exec")
        self.assertIsInstance(block, dict)
        assert isinstance(block, dict)
        self.assertEqual(block.get("gate_id"), live_exec.GATE_ID)
        self.assertFalse(block.get("live_api_called"))

    def test_contract_summary_four_state_cap(self) -> None:
        summary = live_exec.live_proof_exec_contract_summary()
        self.assertEqual(summary["four_state_max"], "TEST_VERIFIED")
        self.assertFalse(summary["live_proof_in_this_pr"])
        self.assertTrue(summary["arc_season_complete"])

    def test_gate_closed_default(self) -> None:
        self.assertTrue(live_exec.live_proof_exec_gate_closed())

    def test_bounded_smoke_steps_nonempty(self) -> None:
        steps = live_exec.bounded_smoke_steps()
        self.assertGreaterEqual(len(steps), 5)
        ids = {s["step_id"] for s in steps}
        self.assertIn("spine-verify", ids)
        self.assertIn("audit-flip", ids)

    def test_run_fixture_suite_counts(self) -> None:
        pos, neg, errors = live_exec.run_fixture_suite()
        self.assertEqual(errors, [])
        self.assertGreaterEqual(pos, 1)
        self.assertGreaterEqual(neg, 5)

    def test_verify_live_proof_exec_script_exit_zero(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "verify_kilo_live_proof_exec.py")],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

    def test_verify_spine_exit_zero(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "verify_kilo_spine.py")],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

    def test_verify_live_flag_fail_closed_without_env(self) -> None:
        env = live_exec.minimal_live_proof_exec_environ()
        proc = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "verify_kilo_live_proof_exec.py"),
                "--live",
            ],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            env={**env, "PATH": os.environ.get("PATH", "")},
        )
        self.assertEqual(proc.returncode, 1)

    def test_runbook_live_proof_exec_section(self) -> None:
        text = spine.load_text(spine.runbook_path())
        self.assertIn("live-proof-exec", text)
        self.assertIn("verify_kilo_live_proof_exec", text)

    def test_season_close_marker_constant(self) -> None:
        self.assertIn("141-150", live_exec.ARC_SEASON_COMPLETE)
        self.assertIn("standby", live_exec.CLOUD_BOT_STANDBY_AFTER_MERGE.lower())

    def test_module_doc_no_forbidden_literals(self) -> None:
        self.assertEqual(spine.find_forbidden_literal_claims(live_exec.__doc__ or ""), [])

    def test_redaction_on_summary_dump(self) -> None:
        dumped = json.dumps(live_exec.live_proof_exec_contract_summary())
        self.assertNotIn("sk-live", dumped)

    def test_audit_flip_procedure_documented(self) -> None:
        steps = live_exec.audit_flip_procedure()
        self.assertTrue(any("live_verified" in s for s in steps))

    def test_guide_exists(self) -> None:
        path = REPO_ROOT / "docs/guides/kilo_live_proof_exec.md"
        self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
