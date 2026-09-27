"""Hermetic gates for PR #146 KILO mercury-hermetic (gate ``mercury-hermetic``)."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from thinkbox import kilo_env_matrix as matrix
from thinkbox import kilo_governance_evidence as governance
from thinkbox import kilo_live_proof_readiness as spine
from thinkbox import kilo_mercury_hermetic as mercury
from thinkbox.cli_live_gate import swarm_live_authorization_report
from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.identity import IdentityLedger

REPO_ROOT = Path(__file__).resolve().parents[2]


def _issued_token() -> tuple[GovernanceTokenService, IdentityLedger, str]:
    tokens = GovernanceTokenService(signing_key="pr146-test-key")
    identities = IdentityLedger()
    identities.register(
        agent_id="kilo-live-proof-agent",
        capabilities=["kilo:live_burst"],
        policy_version="kilo-live-proof-v1",
    )
    issued = tokens.issue(
        TokenRequest(
            agent_id="kilo-live-proof-agent",
            capabilities=["kilo:live_burst"],
            policy_version="kilo-live-proof-v1",
            ttl_seconds=3600.0,
        )
    )
    return tokens, identities, issued.token_value


class TestMercuryGate(unittest.TestCase):
    def test_pr146_gate_id(self) -> None:
        gate = spine.gate_for_pr(146)
        self.assertIsNotNone(gate)
        assert gate is not None
        self.assertEqual(gate.gate_id, mercury.GATE_ID)
        self.assertEqual(mercury.PR_NUMBER, 146)

    def test_arc_includes_mercury_hermetic(self) -> None:
        self.assertIn("mercury-hermetic", spine.gate_ids())

    def test_hermetic_unit_passes_with_mock_and_token(self) -> None:
        env = mercury.minimal_mercury_hermetic_environ()
        tokens, identities, token_value = _issued_token()
        result = mercury.evaluate_mercury_hermetic(
            matrix.EnvMatrixMode.HERMETIC_UNIT,
            env,
            token_value=token_value,
            tokens=tokens,
            identities=identities,
        )
        self.assertTrue(result.ok, msg=result.violations)
        self.assertTrue(result.governance_evidence_ok)
        assert result.evidence is not None
        self.assertFalse(result.evidence.live_api_called)
        self.assertIsNotNone(result.evidence.mock_call)

    def test_mock_not_configured_denied(self) -> None:
        env = governance.minimal_governance_hermetic_environ()
        tokens, identities, token_value = _issued_token()
        result = mercury.evaluate_mercury_hermetic(
            matrix.EnvMatrixMode.HERMETIC_UNIT,
            env,
            token_value=token_value,
            tokens=tokens,
            identities=identities,
        )
        self.assertFalse(result.ok)
        codes = {v.code for v in result.violations}
        self.assertIn("mercury_mock_not_configured", codes)

    def test_requires_governance_layer(self) -> None:
        env = mercury.minimal_mercury_hermetic_environ({"THINKBOX_SWARM_LIVE_ACK": "1"})
        tokens, identities, token_value = _issued_token()
        result = mercury.evaluate_mercury_hermetic(
            matrix.EnvMatrixMode.HERMETIC_UNIT,
            env,
            token_value=token_value,
            tokens=tokens,
            identities=identities,
        )
        self.assertFalse(result.ok)
        self.assertFalse(result.governance_evidence_ok)

    def test_invalid_fixture_denied(self) -> None:
        env = mercury.minimal_mercury_hermetic_environ()
        tokens, identities, token_value = _issued_token()
        result = mercury.evaluate_mercury_hermetic(
            matrix.EnvMatrixMode.HERMETIC_UNIT,
            env,
            token_value=token_value,
            tokens=tokens,
            identities=identities,
            fixture_id="nonexistent",
        )
        self.assertFalse(result.ok)


class TestMockClient(unittest.TestCase):
    def test_bounded_client_no_network(self) -> None:
        client = mercury.BoundedMercuryMockClient()
        out = client.complete("probe")
        self.assertFalse(out.live_api_called)
        self.assertEqual(out.model, mercury.MERCURY_HERMETIC_MODEL)
        json.loads(out.content)

    def test_fixtures_bounded_count(self) -> None:
        fixtures = mercury.bounded_mercury_fixtures()
        self.assertGreaterEqual(len(fixtures), 3)
        for _fid, body in fixtures.items():
            self.assertIn("content", body)

    def test_mock_client_configured_flag(self) -> None:
        env = mercury.minimal_mercury_hermetic_environ()
        self.assertTrue(mercury.mock_client_configured(env))
        clean = governance.minimal_governance_hermetic_environ()
        self.assertFalse(mercury.mock_client_configured(clean))

    def test_mock_url_without_flag(self) -> None:
        env = governance.minimal_governance_hermetic_environ(
            {"THINKBOX_MERCURY_BASE_URL": "mock://mercury"}
        )
        self.assertTrue(mercury.mock_client_configured(env))


class TestLiveGateAlignment(unittest.TestCase):
    def test_align_live_gate_stub(self) -> None:
        report = mercury.align_live_gate_stub({})
        base = swarm_live_authorization_report()
        self.assertEqual(report["authorized"], base["authorized"])
        self.assertFalse(report["live_api_called"])
        self.assertEqual(report["gate_id"], mercury.GATE_ID)
        self.assertFalse(report["mercury_network_io"])

    def test_live_gate_authorized_without_network(self) -> None:
        env = mercury.minimal_mercury_hermetic_environ(
            {
                "INCEPTION_API_KEY": "mock_inception_key_for_test",
                "THINKBOX_SWARM_LIVE_ACK": "1",
            }
        )
        report = mercury.align_live_gate_stub(env)
        self.assertTrue(report["authorized"])
        self.assertFalse(report["live_api_called"])

    def test_live_gate_denied_without_ack(self) -> None:
        env = mercury.minimal_mercury_hermetic_environ(
            {"INCEPTION_API_KEY": "mock_inception_key_for_test"}
        )
        report = mercury.align_live_gate_stub(env)
        self.assertFalse(report["authorized"])

    def test_evidence_includes_live_gate_report(self) -> None:
        env = mercury.minimal_mercury_hermetic_environ()
        tokens, identities, token_value = _issued_token()
        result = mercury.evaluate_mercury_hermetic(
            matrix.EnvMatrixMode.HERMETIC_UNIT,
            env,
            token_value=token_value,
            tokens=tokens,
            identities=identities,
        )
        assert result.evidence is not None
        self.assertEqual(
            result.evidence.live_gate_report.get("mode"),
            "authorization_check_only",
        )


class TestOperatorAndSummary(unittest.TestCase):
    def test_hermetic_operator_ok_clean_env(self) -> None:
        env = mercury.minimal_mercury_hermetic_environ()
        op = mercury.hermetic_mercury_operator_check(env)
        self.assertTrue(op.ok, msg=op.violations)

    def test_forbidden_provider_without_mock(self) -> None:
        env = governance.minimal_governance_hermetic_environ(
            {"INCEPTION_API_KEY": "sk-live-production-shaped-key"}
        )
        op = mercury.hermetic_mercury_operator_check(env)
        self.assertFalse(op.ok)

    def test_contract_summary_redacted(self) -> None:
        summary = mercury.mercury_hermetic_contract_summary(
            {"INCEPTION_API_KEY": "must-not-appear-in-summary"}
        )
        dumped = json.dumps(summary)
        self.assertNotIn("must-not-appear-in-summary", dumped)
        self.assertEqual(summary["gate_id"], mercury.GATE_ID)
        self.assertFalse(summary["live_api_called"])

    def test_gate_closed_default(self) -> None:
        self.assertTrue(mercury.mercury_hermetic_gate_closed())

    def test_spine_summary_includes_pr146(self) -> None:
        summary = spine.spine_contract_summary()
        self.assertEqual(summary.get("pr146_gate_id"), mercury.GATE_ID)
        block = summary.get("mercury_hermetic")
        self.assertIsInstance(block, dict)
        assert isinstance(block, dict)
        self.assertTrue(block.get("hermetic_operator_ok"))

    def test_redact_mercury_summary(self) -> None:
        text = mercury.redact_mercury_summary('{"INCEPTION_API_KEY": "secret"}')
        self.assertNotIn("secret", text)


class TestRunbookAndDocs(unittest.TestCase):
    def test_runbook_mercury_hermetic_section(self) -> None:
        text = spine.load_text(spine.runbook_path())
        self.assertIn("mercury-hermetic", text)
        self.assertIn("PR #146", text)

    def test_runbook_h10_prerequisite(self) -> None:
        text = spine.load_text(spine.runbook_path())
        self.assertIn("verify_kilo_mercury_hermetic", text)

    def test_arc_doc_pr146_theme(self) -> None:
        text = spine.load_text(spine.arc_doc_path())
        self.assertIn("mercury-hermetic", text)
        self.assertIn("#146", text)

    def test_no_forbidden_literals_in_mercury_module_doc(self) -> None:
        self.assertEqual(
            spine.find_forbidden_literal_claims(mercury.__doc__ or ""),
            [],
        )


class TestVerifyScripts(unittest.TestCase):
    def test_verify_mercury_hermetic_script_exists(self) -> None:
        path = REPO_ROOT / "scripts" / "verify_kilo_mercury_hermetic.py"
        self.assertTrue(path.is_file())

    def test_verify_mercury_hermetic_exit_zero(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "verify_kilo_mercury_hermetic.py")],
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
    def test_audit_checklist_pr146_exists(self) -> None:
        path = REPO_ROOT / "docs/audit/checklists/kilo-mercury-hermetic-pr146.md"
        self.assertTrue(path.is_file())

    def test_audit_pass_pr146_live_verified_false(self) -> None:
        path = REPO_ROOT / "docs/audit/passes/2026-09-23-pr146.json"
        self.assertTrue(path.is_file())
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(data["four_state"]["live_verified"])


class TestEvidenceSerialization(unittest.TestCase):
    def test_evidence_to_dict_no_secrets(self) -> None:
        env = mercury.minimal_mercury_hermetic_environ()
        tokens, identities, token_value = _issued_token()
        result = mercury.evaluate_mercury_hermetic(
            matrix.EnvMatrixMode.HERMETIC_UNIT,
            env,
            token_value=token_value,
            tokens=tokens,
            identities=identities,
        )
        payload = json.dumps(result.to_dict())
        self.assertNotIn(token_value, payload)
        self.assertIn("mercury-hermetic", payload)
        self.assertIn('"live_api_called": false', payload)

    def test_reasoning_field_in_mock_call(self) -> None:
        client = mercury.BoundedMercuryMockClient(fixture_id="think_token")
        out = client.complete("x")
        self.assertIsNotNone(out.reasoning)


if __name__ == "__main__":
    unittest.main()
