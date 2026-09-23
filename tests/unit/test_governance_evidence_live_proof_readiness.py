"""Unit tests for governance-evidence Live-proof readiness helpers (PR #164)."""

from __future__ import annotations

import unittest

from thinkbox.governance_evidence_live_proof_readiness import (
    READINESS_SCHEMA_VERSION,
    evaluate_governance_evidence_hermetic_unit,
    governance_evidence_live_proof_readiness_contract_snippet,
    live_proof_prereqs_satisfied,
    minimal_valid_readiness_document,
    validate_readiness_document,
)
from thinkbox.kilo_governance_evidence import minimal_governance_hermetic_environ
from thinkbox.kilo_governance_evidence_live_proof_readiness import (
    GATE_ID,
    PR_NUMBER,
    PRIOR_GATE_IDS,
)
from thinkbox.kilo_live_proof_exec import FOUNDER_ACK_ENV
from thinkbox.kilo_substrate_checklist import BOX_URL_ENV


class TestGovernanceEvidenceLiveProofReadiness(unittest.TestCase):
    def test_contract_snippet_honesty(self) -> None:
        snippet = governance_evidence_live_proof_readiness_contract_snippet()
        self.assertFalse(snippet.get("live_verified", True))
        self.assertFalse(snippet.get("live_api_called", True))
        self.assertEqual(snippet.get("four_state_max"), "TEST_VERIFIED")

    def test_minimal_readiness_document_valid(self) -> None:
        doc = minimal_valid_readiness_document(
            gate_id=GATE_ID,
            pr_number=PR_NUMBER,
            prior_gate_ids=list(PRIOR_GATE_IDS),
        )
        result = validate_readiness_document(doc)
        self.assertTrue(result.ok, msg=[v.message for v in result.violations])
        self.assertEqual(doc["schema_version"], READINESS_SCHEMA_VERSION)

    def test_live_verified_true_fails_validation(self) -> None:
        doc = minimal_valid_readiness_document(
            gate_id=GATE_ID,
            pr_number=PR_NUMBER,
            prior_gate_ids=list(PRIOR_GATE_IDS),
        )
        doc["live_verified"] = True
        result = validate_readiness_document(doc)
        self.assertFalse(result.ok)

    def test_hermetic_unit_governance_evidence_passes(self) -> None:
        env = minimal_governance_hermetic_environ()
        ok, payload = evaluate_governance_evidence_hermetic_unit(env)
        self.assertTrue(ok, msg=payload)
        self.assertFalse(payload.get("live_api_called", True))

    def test_live_prereqs_not_satisfied_in_hermetic_env(self) -> None:
        env = minimal_governance_hermetic_environ()
        self.assertFalse(live_proof_prereqs_satisfied(env))

    def test_live_prereqs_satisfied_when_documented_keys_set(self) -> None:
        env = {
            FOUNDER_ACK_ENV: "true",
            BOX_URL_ENV: "https://example-3000.preview.box.upstash.com",
        }
        self.assertTrue(live_proof_prereqs_satisfied(env))


if __name__ == "__main__":
    unittest.main()
