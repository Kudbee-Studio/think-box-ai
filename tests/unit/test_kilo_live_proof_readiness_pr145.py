"""Hermetic gates for PR #145 KILO governance-evidence (gate ``governance-evidence``)."""

from __future__ import annotations

import json
import subprocess
import sys
import time
import unittest
from pathlib import Path

from thinkbox import kilo_env_matrix as matrix
from thinkbox import kilo_governance_evidence as governance
from thinkbox import kilo_live_proof_readiness as spine
from thinkbox import kilo_substrate_checklist as substrate
from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.identity import IdentityLedger

REPO_ROOT = Path(__file__).resolve().parents[2]


def _issued_token(
    agent_id: str = "kilo-live-proof-agent",
    capability: str = "kilo:live_burst",
) -> tuple[GovernanceTokenService, IdentityLedger, str]:
    tokens = GovernanceTokenService(signing_key="pr145-test-key")
    identities = IdentityLedger()
    identities.register(
        agent_id=agent_id,
        capabilities=[capability],
        policy_version="kilo-live-proof-v1",
    )
    issued = tokens.issue(
        TokenRequest(
            agent_id=agent_id,
            capabilities=[capability],
            policy_version="kilo-live-proof-v1",
            ttl_seconds=3600.0,
        )
    )
    return tokens, identities, issued.token_value


class TestGovernanceGate(unittest.TestCase):
    def test_pr145_gate_id(self) -> None:
        gate = spine.gate_for_pr(145)
        self.assertIsNotNone(gate)
        assert gate is not None
        self.assertEqual(gate.gate_id, governance.GATE_ID)

    def test_pr144_ci_post_merge_gate_id(self) -> None:
        gate = spine.gate_for_pr(144)
        self.assertIsNotNone(gate)
        assert gate is not None
        self.assertEqual(gate.gate_id, "ci-post-merge")

    def test_pr146_mercury_hermetic_gate_id(self) -> None:
        gate = spine.gate_for_pr(146)
        self.assertIsNotNone(gate)
        assert gate is not None
        self.assertEqual(gate.gate_id, "mercury-hermetic")

    def test_hermetic_unit_clean_passes_with_token(self) -> None:
        env = governance.minimal_governance_hermetic_environ()
        tokens, identities, token_value = _issued_token()
        result = governance.evaluate_governance_evidence(
            matrix.EnvMatrixMode.HERMETIC_UNIT,
            env,
            token_value=token_value,
            tokens=tokens,
            identities=identities,
        )
        self.assertTrue(result.ok, msg=result.violations)
        self.assertTrue(result.env_matrix_ok)
        self.assertTrue(result.substrate_checklist_ok)
        self.assertIsNotNone(result.evidence)
        assert result.evidence is not None
        self.assertTrue(result.evidence.admission_allowed)
        self.assertFalse(result.evidence.live_api_called)

    def test_token_missing_denied(self) -> None:
        env = governance.minimal_governance_hermetic_environ()
        result = governance.evaluate_governance_evidence(
            matrix.EnvMatrixMode.HERMETIC_UNIT,
            env,
            token_value=None,
        )
        self.assertFalse(result.ok)
        codes = {v.code for v in result.violations}
        self.assertIn("token_missing", codes)

    def test_expired_token_denied(self) -> None:
        env = governance.minimal_governance_hermetic_environ()
        tokens, identities, token_value = _issued_token()
        result = governance.evaluate_governance_evidence(
            matrix.EnvMatrixMode.HERMETIC_UNIT,
            env,
            token_value=token_value,
            tokens=tokens,
            identities=identities,
            now=time.time() + 7200,
        )
        self.assertFalse(result.ok)
        self.assertIn("token_invalid_or_expired", {v.code for v in result.violations})

    def test_revoked_token_denied(self) -> None:
        env = governance.minimal_governance_hermetic_environ()
        tokens, identities, token_value = _issued_token()
        tokens.revoke(token_value)
        result = governance.evaluate_governance_evidence(
            matrix.EnvMatrixMode.HERMETIC_UNIT,
            env,
            token_value=token_value,
            tokens=tokens,
            identities=identities,
        )
        self.assertFalse(result.ok)

    def test_capability_miss_denied(self) -> None:
        env = governance.minimal_governance_hermetic_environ()
        tokens, identities, token_value = _issued_token()
        result = governance.evaluate_governance_evidence(
            matrix.EnvMatrixMode.HERMETIC_UNIT,
            env,
            capability="kilo:other",
            token_value=token_value,
            tokens=tokens,
            identities=identities,
        )
        self.assertFalse(result.ok)
        self.assertIn("capability_not_granted", {v.code for v in result.violations})

    def test_agent_mismatch_denied(self) -> None:
        env = governance.minimal_governance_hermetic_environ()
        tokens, identities, token_value = _issued_token()
        result = governance.evaluate_governance_evidence(
            matrix.EnvMatrixMode.HERMETIC_UNIT,
            env,
            agent_id="other-agent",
            token_value=token_value,
            tokens=tokens,
            identities=identities,
        )
        self.assertFalse(result.ok)
        self.assertIn("token_agent_mismatch", {v.code for v in result.violations})

    def test_requires_env_matrix_layer(self) -> None:
        env = governance.minimal_governance_hermetic_environ(
            {"THINKBOX_SWARM_LIVE_ACK": "1"}
        )
        tokens, identities, token_value = _issued_token()
        result = governance.evaluate_governance_evidence(
            matrix.EnvMatrixMode.HERMETIC_UNIT,
            env,
            token_value=token_value,
            tokens=tokens,
            identities=identities,
        )
        self.assertFalse(result.ok)
        self.assertFalse(result.env_matrix_ok)

    def test_requires_substrate_layer(self) -> None:
        env = governance.minimal_governance_hermetic_environ(
            {
                "UPSTASH_PUBLIC_BOX_URL": "https://live.preview.box.upstash.com",
                "UPSTASH_PUBLIC_BOX_TOKEN": "abcdefghij",
            }
        )
        tokens, identities, token_value = _issued_token()
        result = governance.evaluate_governance_evidence(
            matrix.EnvMatrixMode.HERMETIC_UNIT,
            env,
            token_value=token_value,
            tokens=tokens,
            identities=identities,
        )
        self.assertFalse(result.ok)
        self.assertFalse(result.substrate_checklist_ok)


class TestEvidenceShape(unittest.TestCase):
    def test_token_fingerprint_never_raw(self) -> None:
        raw = "govt.payload.sig"
        fp = governance.token_fingerprint(raw)
        self.assertIsNotNone(fp)
        assert fp is not None
        self.assertNotIn(raw, fp)
        self.assertTrue(fp.startswith("sha256:"))

    def test_redact_secret_value(self) -> None:
        self.assertIn("redacted", governance.redact_secret_value("INCEPTION_API_KEY", "sk-live-secret"))
        self.assertEqual(
            governance.redact_secret_value("UPSTASH_PUBLIC_BOX_TOKEN", "abcdefghij"),
            substrate.redact_box_token("abcdefghij"),
        )

    def test_evidence_to_dict_fields(self) -> None:
        env = governance.minimal_governance_hermetic_environ()
        tokens, identities, token_value = _issued_token()
        result = governance.evaluate_governance_evidence(
            matrix.EnvMatrixMode.HERMETIC_UNIT,
            env,
            token_value=token_value,
            tokens=tokens,
            identities=identities,
        )
        payload = json.dumps(result.to_dict())
        self.assertNotIn(token_value, payload)
        self.assertIn("governance-evidence", payload)
        self.assertIn('"live_api_called": false', payload)

    def test_evidence_label_allowed_values(self) -> None:
        from thinkbox.admission import AdmissionDecision

        ev = governance.build_live_burst_evidence(
            agent_id="a",
            capability="c",
            policy_version="p",
            decision=AdmissionDecision(True, "admitted", "a", "c"),
            token_value="govt.x.y",
            env_matrix_ok=True,
            substrate_checklist_ok=True,
            env_matrix_ref={},
            substrate_ref={},
            evidence_label="inferred",
        )
        self.assertEqual(ev.evidence_label, "inferred")


class TestOperatorAndSummary(unittest.TestCase):
    def test_hermetic_operator_ok_clean_env(self) -> None:
        env = governance.minimal_governance_hermetic_environ()
        op = governance.hermetic_governance_operator_check(env)
        self.assertTrue(op.ok, msg=op.violations)

    def test_forbidden_governance_token_in_hermetic(self) -> None:
        env = governance.minimal_governance_hermetic_environ(
            {"THINKBOX_GOVERNANCE_TOKEN": "production-token-value-here"}
        )
        op = governance.hermetic_governance_operator_check(env)
        self.assertFalse(op.ok)

    def test_contract_summary_redacted(self) -> None:
        summary = governance.governance_evidence_contract_summary(
            {"INCEPTION_API_KEY": "must-not-appear"}
        )
        dumped = json.dumps(summary)
        self.assertNotIn("must-not-appear", dumped)
        self.assertEqual(summary["gate_id"], governance.GATE_ID)
        self.assertFalse(summary["live_api_called"])

    def test_gate_closed_default(self) -> None:
        self.assertTrue(governance.governance_evidence_gate_closed())

    def test_spine_summary_includes_pr145(self) -> None:
        summary = spine.spine_contract_summary()
        self.assertEqual(summary.get("pr145_gate_id"), governance.GATE_ID)
        block = summary.get("governance_evidence")
        self.assertIsInstance(block, dict)
        assert isinstance(block, dict)
        self.assertTrue(block.get("hermetic_operator_ok"))


class TestRunbookAndDocs(unittest.TestCase):
    def test_runbook_governance_evidence_section(self) -> None:
        text = spine.load_text(spine.runbook_path())
        self.assertIn("governance-evidence", text)
        self.assertIn("PR #145", text)
        self.assertIn("PR #144", text)

    def test_arc_doc_pr145_theme(self) -> None:
        text = spine.load_text(spine.arc_doc_path())
        self.assertIn("governance-evidence", text)
        self.assertIn("#145", text)

    def test_runbook_h9_prerequisite(self) -> None:
        text = spine.load_text(spine.runbook_path())
        self.assertIn("verify_kilo_governance_evidence", text)

    def test_no_forbidden_literals_in_governance_module_doc(self) -> None:
        self.assertEqual(
            spine.find_forbidden_literal_claims(governance.__doc__ or ""),
            [],
        )


class TestVerifyScripts(unittest.TestCase):
    def test_verify_governance_evidence_script_exists(self) -> None:
        path = REPO_ROOT / "scripts" / "verify_kilo_governance_evidence.py"
        self.assertTrue(path.is_file())

    def test_verify_governance_evidence_exit_zero(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "verify_kilo_governance_evidence.py")],
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


class TestAuditArtifacts(unittest.TestCase):
    def test_audit_checklist_pr145_exists(self) -> None:
        path = REPO_ROOT / "docs/audit/checklists/kilo-governance-evidence-pr145.md"
        self.assertTrue(path.is_file())

    def test_audit_pass_pr145_live_verified_false(self) -> None:
        path = REPO_ROOT / "docs/audit/passes/2026-09-23-pr145.json"
        self.assertTrue(path.is_file())
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(data["four_state"]["live_verified"])


if __name__ == "__main__":
    unittest.main()
