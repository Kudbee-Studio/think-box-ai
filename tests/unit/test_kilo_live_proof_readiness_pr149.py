"""Hermetic gates for PR #149 KILO dashboard-slots (gate ``dashboard-slots``)."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from thinkbox import kilo_dashboard_slots as dashboard_slots
from thinkbox import kilo_live_proof_readiness as spine
from thinkbox import kilo_proof_schema as proof_schema
from thinkbox.kilo_env_matrix import EnvMatrixMode

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestDashboardSlotsGate(unittest.TestCase):
    def test_pr149_gate_id(self) -> None:
        gate = spine.gate_for_pr(149)
        self.assertIsNotNone(gate)
        assert gate is not None
        self.assertEqual(gate.gate_id, dashboard_slots.GATE_ID)
        self.assertEqual(dashboard_slots.PR_NUMBER, 149)

    def test_arc_includes_dashboard_slots(self) -> None:
        self.assertIn("dashboard-slots", spine.gate_ids())

    def test_hermetic_unit_passes_clean_env(self) -> None:
        env = dashboard_slots.minimal_dashboard_slots_environ()
        result = dashboard_slots.evaluate_dashboard_slots(EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertTrue(result.ok, msg=result.violations)
        self.assertTrue(result.proof_schema_ok)
        assert result.evidence is not None
        self.assertFalse(result.evidence.live_api_called)

    def test_requires_proof_schema_layer(self) -> None:
        env = dashboard_slots.minimal_dashboard_slots_environ()
        env = dict(env)
        env.pop("THINKBOX_KILO_MERCURY_MOCK", None)
        env.pop("THINKBOX_MERCURY_BASE_URL", None)
        env["INCEPTION_API_KEY"] = "sk-live-production-shaped-key"
        result = dashboard_slots.evaluate_dashboard_slots(EnvMatrixMode.HERMETIC_UNIT, env)
        self.assertFalse(result.ok)
        self.assertFalse(result.proof_schema_ok)


class TestSlotRegistryValidation(unittest.TestCase):
    def test_minimal_registry_valid(self) -> None:
        doc = dashboard_slots.minimal_valid_slot_registry_document()
        result = dashboard_slots.validate_slot_registry_document(doc)
        self.assertTrue(result.ok, msg=result.violations)

    def test_valid_minimal_fixture(self) -> None:
        doc = dashboard_slots.load_fixture("valid_minimal.json")
        self.assertTrue(dashboard_slots.validate_slot_registry_document(doc).ok)

    def test_valid_multiplex_shared_fixture(self) -> None:
        doc = dashboard_slots.load_fixture("valid_multiplex_shared.json")
        self.assertTrue(dashboard_slots.validate_slot_registry_document(doc).ok)

    def test_missing_bind_fails(self) -> None:
        doc = dashboard_slots.load_fixture("invalid_missing_bind.json")
        codes = {v.code for v in dashboard_slots.validate_slot_registry_document(doc).violations}
        self.assertIn("slot_unbound", codes)

    def test_stale_etag_fails(self) -> None:
        doc = dashboard_slots.load_fixture("invalid_stale_etag.json")
        codes = {v.code for v in dashboard_slots.validate_slot_registry_document(doc).violations}
        self.assertIn("etag_stale", codes)

    def test_exclusive_multiplex_conflict(self) -> None:
        doc = dashboard_slots.load_fixture("invalid_exclusive_multiplex.json")
        codes = {v.code for v in dashboard_slots.validate_slot_registry_document(doc).violations}
        self.assertIn("multiplex_exclusive_conflict", codes)

    def test_slot_cycle_rejected(self) -> None:
        doc = dashboard_slots.load_fixture("invalid_cycle.json")
        codes = {v.code for v in dashboard_slots.validate_slot_registry_document(doc).violations}
        self.assertIn("slot_dependency_cycle", codes)

    def test_injected_cue_not_user_intent(self) -> None:
        doc = dashboard_slots.load_fixture("invalid_injected_cue.json")
        codes = {v.code for v in dashboard_slots.validate_slot_registry_document(doc).violations}
        self.assertIn("injected_cue_not_user_intent", codes)

    def test_live_api_called_forbidden(self) -> None:
        doc = dashboard_slots.load_fixture("invalid_live_api_called.json")
        codes = {v.code for v in dashboard_slots.validate_slot_registry_document(doc).violations}
        self.assertIn("live_api_forbidden", codes)

    def test_live_verified_forbidden(self) -> None:
        doc = dashboard_slots.load_fixture("invalid_live_verified.json")
        codes = {v.code for v in dashboard_slots.validate_slot_registry_document(doc).violations}
        self.assertIn("live_verified_forbidden", codes)

    def test_dashboard_live_claim_forbidden(self) -> None:
        doc = dashboard_slots.load_fixture("invalid_dashboard_live_claim.json")
        codes = {v.code for v in dashboard_slots.validate_slot_registry_document(doc).violations}
        self.assertIn("dashboard_live_claim_forbidden", codes)

    def test_multiplex_digest_identity_stable(self) -> None:
        a = dashboard_slots.build_multiplex_digest_identity("rcpt_a", "etag_b", dashboard_revision=3)
        b = dashboard_slots.build_multiplex_digest_identity("rcpt_a", "etag_b", dashboard_revision=3)
        self.assertEqual(a, b)
        self.assertNotEqual(
            a,
            dashboard_slots.build_multiplex_digest_identity("rcpt_a", "etag_c", dashboard_revision=3),
        )

    def test_proof_document_cross_check(self) -> None:
        registry = dashboard_slots.minimal_valid_slot_registry_document()
        proof = proof_schema.minimal_valid_proof_document()
        bad = dashboard_slots.validate_slot_registry_document(registry, proof_document=proof)
        self.assertFalse(bad.ok)
        codes = {v.code for v in bad.violations}
        self.assertTrue("proof_receipt_mismatch" in codes or "proof_etag_mismatch" in codes)


class TestSpineAndOperators(unittest.TestCase):
    def test_spine_includes_dashboard_slots_block(self) -> None:
        summary = spine.spine_contract_summary()
        self.assertEqual(summary.get("pr149_gate_id"), dashboard_slots.GATE_ID)
        block = summary.get("dashboard_slots")
        self.assertIsInstance(block, dict)
        assert isinstance(block, dict)
        self.assertEqual(block.get("gate_id"), dashboard_slots.GATE_ID)
        self.assertFalse(block.get("live_api_called"))

    def test_contract_summary_four_state_cap(self) -> None:
        summary = dashboard_slots.dashboard_slots_contract_summary()
        self.assertEqual(summary["four_state_max"], "TEST_VERIFIED")
        self.assertFalse(summary["live_proof_in_this_pr"])

    def test_gate_closed_default(self) -> None:
        self.assertTrue(dashboard_slots.dashboard_slots_gate_closed())

    def test_slot_kinds_cover_enums(self) -> None:
        self.assertIn("proof_receipt", dashboard_slots.SLOT_KINDS)
        self.assertIn("dod_checklist", dashboard_slots.SLOT_KINDS)

    def test_registry_json_schema(self) -> None:
        schema = dashboard_slots.slot_registry_json_schema()
        self.assertEqual(schema["gate_id"], dashboard_slots.GATE_ID)

    def test_run_fixture_suite_counts(self) -> None:
        pos, neg, errors = dashboard_slots.run_fixture_suite()
        self.assertEqual(errors, [])
        self.assertGreaterEqual(pos, 2)
        self.assertGreaterEqual(neg, 7)

    def test_verify_dashboard_slots_script_exists(self) -> None:
        path = REPO_ROOT / "scripts" / "verify_kilo_dashboard_slots.py"
        self.assertTrue(path.is_file())

    def test_verify_dashboard_slots_exit_zero(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "verify_kilo_dashboard_slots.py")],
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

    def test_runbook_dashboard_slots_section(self) -> None:
        text = spine.load_text(spine.runbook_path())
        self.assertIn("dashboard-slots", text)
        self.assertIn("verify_kilo_dashboard_slots", text)

    def test_dashboard_slots_guide_exists(self) -> None:
        path = REPO_ROOT / "docs/guides/kilo_dashboard_slots.md"
        self.assertTrue(path.is_file())

    def test_module_doc_no_forbidden_literals(self) -> None:
        self.assertEqual(spine.find_forbidden_literal_claims(dashboard_slots.__doc__ or ""), [])

    def test_redaction_on_summary_dump(self) -> None:
        dumped = json.dumps(dashboard_slots.dashboard_slots_contract_summary())
        self.assertNotIn("sk-live", dumped)

    def test_occupancy_bound_on_minimal(self) -> None:
        doc = dashboard_slots.minimal_valid_slot_registry_document()
        result = dashboard_slots.validate_slot_registry_document(doc)
        self.assertEqual(result.occupancy.get("slot-proof-receipt"), "bound")

    def test_cannot_infer_live_from_slots_alone(self) -> None:
        doc = dashboard_slots.minimal_valid_slot_registry_document()
        self.assertFalse(doc.get("live_verified"))
        summary = dashboard_slots.dashboard_slots_contract_summary()
        self.assertFalse(summary.get("live_api_called"))


if __name__ == "__main__":
    unittest.main()
