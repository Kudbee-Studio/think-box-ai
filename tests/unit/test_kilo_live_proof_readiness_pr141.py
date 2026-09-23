"""Hermetic gates for PR #141 KILO Live-proof readiness spine."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from thinkbox import kilo_live_proof_readiness as spine


REPO_ROOT = Path(__file__).resolve().parents[2]


class TestRunbookContract(unittest.TestCase):
    def test_runbook_file_exists(self) -> None:
        self.assertTrue(spine.runbook_path().is_file())

    def test_required_headings_present(self) -> None:
        missing = spine.missing_runbook_headings()
        self.assertEqual(missing, [], msg=f"missing headings: {missing}")

    def test_runbook_forbids_literal_kilo_live_claims(self) -> None:
        from thinkbox.kilo_live_proof_readiness import _runbook_text_for_claim_scan

        text = _runbook_text_for_claim_scan(spine.load_text(spine.runbook_path()))
        literals = spine.find_forbidden_literal_claims(text)
        self.assertEqual(literals, [])

    def test_runbook_no_affirmative_kilo_live_lines(self) -> None:
        from thinkbox.kilo_live_proof_readiness import _runbook_text_for_claim_scan

        text = _runbook_text_for_claim_scan(spine.load_text(spine.runbook_path()))
        affirm = spine.find_affirmative_kilo_live_claims(text)
        self.assertEqual(affirm, [], msg=f"affirmative claims: {affirm}")

    def test_runbook_contains_do_not_claim_section(self) -> None:
        text = spine.load_text(spine.runbook_path())
        self.assertIn("## Do not claim LIVE VERIFIED", text)


class TestArcDoc(unittest.TestCase):
    def test_arc_doc_exists(self) -> None:
        self.assertTrue(spine.arc_doc_path().is_file())

    def test_arc_lists_ten_prs(self) -> None:
        self.assertEqual(len(spine.ARC_GATES), 10)
        self.assertEqual(spine.arc_pr_numbers()[0], 141)
        self.assertEqual(spine.arc_pr_numbers()[-1], 150)

    def test_gate_ids_unique(self) -> None:
        ids = spine.gate_ids()
        self.assertEqual(len(ids), len(set(ids)))

    def test_pr141_closes_spine_docs_gate(self) -> None:
        gate = spine.gate_for_pr(141)
        self.assertIsNotNone(gate)
        assert gate is not None
        self.assertEqual(gate.gate_id, "spine-docs")

    def test_pr150_live_proof_exec_gate(self) -> None:
        gate = spine.gate_for_pr(150)
        self.assertIsNotNone(gate)
        assert gate is not None
        self.assertEqual(gate.gate_id, "live-proof-exec")

    def test_spine_docs_on_disk(self) -> None:
        missing = spine.missing_spine_docs()
        self.assertEqual(missing, [], msg=f"missing: {missing}")

    def test_agents_mentions_readiness_arc(self) -> None:
        agents = spine.load_text(REPO_ROOT / "AGENTS.md")
        self.assertIn("KILO Live-proof readiness arc", agents)

    def test_continuity_mentions_pr141(self) -> None:
        continuity = spine.load_text(REPO_ROOT / "docs/CONTINUITY.md")
        self.assertIn("PR #141", continuity)

    def test_runbooks_readme_links_runbook(self) -> None:
        readme = spine.load_text(REPO_ROOT / "docs/runbooks/README.md")
        self.assertIn("kilo-live-proof-readiness.md", readme)


class TestSpineModule(unittest.TestCase):
    def test_summary_four_state_cap(self) -> None:
        summary = spine.spine_contract_summary()
        self.assertEqual(summary["four_state_max"], "TEST_VERIFIED")
        self.assertFalse(summary["live_proof_in_this_pr"])

    def test_summary_pr142_gate_id(self) -> None:
        summary = spine.spine_contract_summary()
        self.assertEqual(summary.get("pr142_gate_id"), "env-matrix")
        env_block = summary.get("env_matrix")
        self.assertIsInstance(env_block, dict)

    def test_summary_pr143_gate_id(self) -> None:
        summary = spine.spine_contract_summary()
        self.assertEqual(summary.get("pr143_gate_id"), "substrate-checklist")
        substrate_block = summary.get("substrate_checklist")
        self.assertIsInstance(substrate_block, dict)

    def test_summary_no_missing_contracts(self) -> None:
        summary = spine.spine_contract_summary()
        self.assertEqual(summary["missing_spine_docs"], [])
        self.assertEqual(summary["missing_runbook_headings"], [])


class TestNewSpinePathsOnly(unittest.TestCase):
    """PR #141 additions must not affirm KILO Live proof yet."""

    def test_arc_doc_no_forbidden_literals(self) -> None:
        text = spine.load_text(spine.arc_doc_path())
        self.assertEqual(spine.find_forbidden_literal_claims(text), [])

    def test_module_docstring_hermetic(self) -> None:
        self.assertIn("Hermetic", spine.__doc__ or "")


class TestVerifyScript(unittest.TestCase):
    def test_verify_kilo_spine_script_exists(self) -> None:
        script = REPO_ROOT / "scripts" / "verify_kilo_spine.py"
        self.assertTrue(script.is_file())

    def test_verify_kilo_env_matrix_script_exists(self) -> None:
        script = REPO_ROOT / "scripts" / "verify_kilo_env_matrix.py"
        self.assertTrue(script.is_file())

    def test_verify_kilo_substrate_checklist_script_exists(self) -> None:
        script = REPO_ROOT / "scripts" / "verify_kilo_substrate_checklist.py"
        self.assertTrue(script.is_file())

    def test_audit_checklist_exists(self) -> None:
        path = REPO_ROOT / "docs/audit/checklists/kilo-spine-pr141.md"
        self.assertTrue(path.is_file())

    def test_guide_pointer_exists(self) -> None:
        guide = REPO_ROOT / "docs/guides/kilo_live_proof_readiness.md"
        self.assertTrue(guide.is_file())
        self.assertIn("runbooks/kilo-live-proof-readiness", guide.read_text(encoding="utf-8"))

    def test_verify_kilo_spine_exit_zero(self) -> None:
        import subprocess

        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "verify_kilo_spine.py")],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)


if __name__ == "__main__":
    unittest.main()
