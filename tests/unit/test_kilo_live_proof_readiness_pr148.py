"""Hermetic gates for PR #148 KILO proof-schema (gate ``proof-schema``)."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from thinkbox import kilo_live_proof_readiness as spine
from thinkbox import kilo_proof_schema as proof_schema
from thinkbox import kilo_swarm_instrumentation as swarm
from thinkbox.kilo_env_matrix import EnvMatrixMode

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestProofSchemaGate(unittest.TestCase):
    def test_pr148_gate_id(self) -> None:
        gate = spine.gate_for_pr(148)
        self.assertIsNotNone(gate)
        assert gate is not None
        self.assertEqual(gate.gate_id, proof_schema.GATE_ID)
        self.assertEqual(proof_schema.PR_NUMBER, 148)

    def test_arc_includes_proof_schema(self) -> None:
        self.assertIn("proof-schema", spine.gate_ids())

    def test_hermetic_unit_passes_clean_env(self) -> None:
        env = proof_schema.minimal_proof_schema_environ()
        result = proof_schema.evaluate_proof_schema(EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertTrue(result.ok, msg=result.violations)
        self.assertTrue(result.swarm_instrumentation_ok)
        assert result.evidence is not None
        self.assertFalse(result.evidence.live_api_called)

    def test_requires_swarm_layer(self) -> None:
        env = proof_schema.minimal_proof_schema_environ()
        env = dict(env)
        env.pop("THINKBOX_KILO_MERCURY_MOCK", None)
        env.pop("THINKBOX_MERCURY_BASE_URL", None)
        env["INCEPTION_API_KEY"] = "sk-live-production-shaped-key"
        result = proof_schema.evaluate_proof_schema(EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertFalse(result.ok)
        self.assertFalse(result.swarm_instrumentation_ok)


class TestDocumentValidation(unittest.TestCase):
    def test_minimal_document_valid(self) -> None:
        doc = proof_schema.minimal_valid_proof_document()
        result = proof_schema.validate_proof_document(doc)
        self.assertTrue(result.ok, msg=result.violations)
        self.assertIn("gate-proof-schema", result.ordered_gate_ids)

    def test_valid_minimal_fixture(self) -> None:
        doc = proof_schema.load_fixture("valid_minimal.json")
        self.assertTrue(proof_schema.validate_proof_document(doc).ok)

    def test_valid_cues_deps_fixture(self) -> None:
        doc = proof_schema.load_fixture("valid_with_cues_deps.json")
        result = proof_schema.validate_proof_document(doc)
        self.assertTrue(result.ok, msg=result.violations)
        self.assertEqual(doc["cues"][1]["cue_type"], "injected_nudge")

    def test_missing_required_fails(self) -> None:
        doc = proof_schema.load_fixture("invalid_missing_required.json")
        self.assertFalse(proof_schema.validate_proof_document(doc).ok)

    def test_cycle_rejected(self) -> None:
        doc = proof_schema.load_fixture("invalid_cycle.json")
        codes = {v.code for v in proof_schema.validate_proof_document(doc).violations}
        self.assertIn("dependency_cycle", codes)

    def test_live_claim_without_flag_fails(self) -> None:
        doc = proof_schema.load_fixture("invalid_live_claim.json")
        codes = {v.code for v in proof_schema.validate_proof_document(doc).violations}
        self.assertTrue(
            "four_state_live_claim_without_flag" in codes or "four_state_dod_incomplete" in codes
        )

    def test_unknown_cue_type_fails_closed(self) -> None:
        doc = proof_schema.load_fixture("invalid_unknown_cue.json")
        codes = {v.code for v in proof_schema.validate_proof_document(doc).violations}
        self.assertIn("unknown_cue_type", codes)

    def test_injected_cue_not_user_intent(self) -> None:
        doc = proof_schema.load_fixture("invalid_injected_as_user_intent.json")
        codes = {v.code for v in proof_schema.validate_proof_document(doc).violations}
        self.assertIn("injected_cue_not_user_intent", codes)

    def test_live_api_called_forbidden(self) -> None:
        doc = proof_schema.load_fixture("invalid_live_api_called.json")
        codes = {v.code for v in proof_schema.validate_proof_document(doc).violations}
        self.assertIn("live_api_forbidden", codes)

    def test_topological_order_helper(self) -> None:
        gates = proof_schema.minimal_valid_proof_document()["gates"]
        order = proof_schema.topological_gate_order(gates)
        self.assertLess(order.index("gate-mercury"), order.index("gate-swarm"))

    def test_detect_cycle_true(self) -> None:
        doc = proof_schema.load_fixture("invalid_cycle.json")
        self.assertTrue(proof_schema.detect_dependency_cycle(doc["gates"]))

    def test_json_schema_exports_enums(self) -> None:
        schema = proof_schema.kilo_proof_json_schema()
        props = schema["properties"]
        self.assertIn("injected_nudge", props["cues"]["items"]["properties"]["cue_type"]["enum"])
        self.assertIn("sentinel", props["halt_reason"]["enum"])


class TestOperatorAndSummary(unittest.TestCase):
    def test_hermetic_operator_ok_clean_env(self) -> None:
        env = proof_schema.minimal_proof_schema_environ()
        op = proof_schema.hermetic_proof_schema_operator_check(env)
        self.assertTrue(op.ok, msg=op.violations)

    def test_contract_summary_redacted(self) -> None:
        summary = proof_schema.proof_schema_contract_summary(
            {"INCEPTION_API_KEY": "must-not-appear-in-summary"}
        )
        dumped = json.dumps(summary)
        self.assertNotIn("must-not-appear-in-summary", dumped)
        self.assertEqual(summary["gate_id"], proof_schema.GATE_ID)
        self.assertFalse(summary["live_api_called"])

    def test_gate_closed_default(self) -> None:
        self.assertTrue(proof_schema.proof_schema_gate_closed())

    def test_spine_summary_includes_pr148(self) -> None:
        summary = spine.spine_contract_summary()
        self.assertEqual(summary.get("pr148_gate_id"), proof_schema.GATE_ID)
        block = summary.get("proof_schema")
        self.assertIsInstance(block, dict)
        assert isinstance(block, dict)
        self.assertTrue(block.get("hermetic_operator_ok"))

    def test_fixture_suite_counts(self) -> None:
        pos, neg, errors = proof_schema.run_fixture_suite()
        self.assertEqual(errors, [])
        self.assertEqual(pos, 2)
        self.assertEqual(neg, 6)


class TestRunbookAndDocs(unittest.TestCase):
    def test_runbook_proof_schema_section(self) -> None:
        text = spine.load_text(spine.runbook_path())
        self.assertIn("proof-schema", text)
        self.assertIn("PR #148", text)

    def test_runbook_h12_prerequisite(self) -> None:
        text = spine.load_text(spine.runbook_path())
        self.assertIn("verify_kilo_proof_schema", text)

    def test_arc_doc_pr148_theme(self) -> None:
        text = spine.load_text(spine.arc_doc_path())
        self.assertIn("proof-schema", text)
        self.assertIn("#148", text)

    def test_proof_schema_guide_exists(self) -> None:
        path = REPO_ROOT / "docs/guides/kilo_proof_schema.md"
        self.assertTrue(path.is_file())
        self.assertIn("proof-schema", path.read_text(encoding="utf-8"))

    def test_no_forbidden_literals_in_module_doc(self) -> None:
        self.assertEqual(spine.find_forbidden_literal_claims(proof_schema.__doc__ or ""), [])

    def test_schema_examples_no_secrets(self) -> None:
        dumped = json.dumps(proof_schema.kilo_proof_json_schema())
        self.assertNotIn("sk-", dumped)
        self.assertNotIn("Bearer ", dumped)


class TestVerifyScripts(unittest.TestCase):
    def test_verify_proof_schema_script_exists(self) -> None:
        path = REPO_ROOT / "scripts" / "verify_kilo_proof_schema.py"
        self.assertTrue(path.is_file())

    def test_verify_proof_schema_exit_zero(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "verify_kilo_proof_schema.py")],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

    def test_verify_spine_still_exit_zero(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "verify_kilo_spine.py")],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

    def test_swarm_still_required_before_proof(self) -> None:
        self.assertTrue(swarm.swarm_instrumentation_gate_closed())


class TestAuditArtifacts(unittest.TestCase):
    def test_audit_checklist_pr148_exists(self) -> None:
        path = REPO_ROOT / "docs/audit/checklists/kilo-proof-schema-pr148.md"
        self.assertTrue(path.is_file())

    def test_audit_pass_pr148_live_verified_false(self) -> None:
        path = REPO_ROOT / "docs/audit/passes/2026-09-23-pr148.json"
        self.assertTrue(path.is_file())
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(data["four_state"]["live_verified"])


class TestFourStateHonesty(unittest.TestCase):
    def test_summary_four_state_cap(self) -> None:
        summary = proof_schema.proof_schema_contract_summary()
        self.assertEqual(summary["four_state_max"], "TEST_VERIFIED")
        self.assertFalse(summary["live_proof_in_this_pr"])

    def test_live_verified_true_rejected_in_hermetic_doc(self) -> None:
        doc = proof_schema.minimal_valid_proof_document()
        doc = dict(doc)
        doc["live_verified"] = True
        result = proof_schema.validate_proof_document(doc)
        self.assertFalse(result.ok)
        codes = {v.code for v in result.violations}
        self.assertIn("live_verified_without_dod", codes)

    def test_result_four_state_cap(self) -> None:
        env = proof_schema.minimal_proof_schema_environ()
        result = proof_schema.evaluate_proof_schema(EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertEqual(result.to_dict()["four_state_max"], "TEST_VERIFIED")


if __name__ == "__main__":
    unittest.main()
