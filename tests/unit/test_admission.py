"""Unit tests for thinkbox/admission.py — KUDBEE admission gate."""

import unittest
from thinkbox.admission import AdmissionGate
from thinkbox.governance_token import GovernanceTokenService, TokenRequest
from thinkbox.identity import IdentityLedger


def build_gate() -> tuple[AdmissionGate, GovernanceTokenService, IdentityLedger]:
    tokens = GovernanceTokenService(signing_key="test-key")
    identities = IdentityLedger()
    gate = AdmissionGate(tokens, identities)
    return gate, tokens, identities


class TestAdmissionGate(unittest.TestCase):
    def test_admitted_with_valid_token(self):
        gate, tokens, identities = build_gate()
        identity = identities.register(agent_id="a1", capabilities=["file:read"])
        token = tokens.issue(TokenRequest(agent_id=identity.agent_id, capabilities=["file:read"], ttl_seconds=60.0))
        decision = gate.authorize(token.token_value, "a1", "file:read")
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "admitted")

    def test_fails_closed_without_token(self):
        gate, tokens, identities = build_gate()
        identities.register(agent_id="a1", capabilities=["file:read"])
        decision = gate.authorize("", "a1", "file:read")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "token_invalid_or_expired")

    def test_fails_on_agent_mismatch(self):
        gate, tokens, identities = build_gate()
        identities.register(agent_id="a1", capabilities=["file:read"])
        token = tokens.issue(TokenRequest(agent_id="a1", capabilities=["file:read"]))
        decision = gate.authorize(token.token_value, "a2", "file:read")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "token_agent_mismatch")

    def test_fails_on_missing_capability(self):
        gate, tokens, identities = build_gate()
        identities.register(agent_id="a1", capabilities=["file:read"])
        token = tokens.issue(TokenRequest(agent_id="a1", capabilities=["file:read"]))
        decision = gate.authorize(token.token_value, "a1", "file:write")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "capability_not_granted")

    def test_fails_after_token_revocation(self):
        gate, tokens, identities = build_gate()
        identities.register(agent_id="a1", capabilities=["file:read"])
        token = tokens.issue(TokenRequest(agent_id="a1", capabilities=["file:read"]))
        tokens.revoke(token.token_value)
        decision = gate.authorize(token.token_value, "a1", "file:read")
        self.assertFalse(decision.allowed)

    def test_recent_records_capture_denials(self):
        gate, tokens, identities = build_gate()
        identities.register(agent_id="a1", capabilities=["file:read"])
        gate.authorize("bogus", "a1", "file:read")
        records = gate.recent()
        self.assertEqual(len(records), 1)
        self.assertFalse(records[0]["allowed"])


if __name__ == "__main__":
    unittest.main()