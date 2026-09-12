"""Unit tests for thinkbox/governance_token.py — KUDBEE admission."""

import time
import unittest
from thinkbox.governance_token import GovernanceTokenService, TokenRequest


class TestGovernanceTokenService(unittest.TestCase):
    def test_issue_and_verify(self):
        svc = GovernanceTokenService(signing_key="test-key")
        token = svc.issue(TokenRequest(agent_id="a1", capabilities=["file:read"], ttl_seconds=60.0))
        verified = svc.verify(token.token_value)
        self.assertIsNotNone(verified)
        self.assertEqual(verified.agent_id, "a1")
        self.assertIn("file:read", verified.capabilities)

    def test_expired_token_rejected(self):
        svc = GovernanceTokenService(signing_key="test-key")
        token = svc.issue(TokenRequest(agent_id="a1", ttl_seconds=1.0))
        self.assertIsNone(svc.verify(token.token_value, now=time.time() + 10.0))

    def test_revoke(self):
        svc = GovernanceTokenService(signing_key="test-key")
        token = svc.issue(TokenRequest(agent_id="a1"))
        self.assertTrue(svc.revoke(token.token_value))
        self.assertIsNone(svc.verify(token.token_value))

    def test_revoke_for_agent(self):
        svc = GovernanceTokenService(signing_key="test-key")
        svc.issue(TokenRequest(agent_id="a1"))
        svc.issue(TokenRequest(agent_id="a1"))
        svc.issue(TokenRequest(agent_id="a2"))
        revoked = svc.revoke_for_agent("a1")
        self.assertEqual(revoked, 2)

    def test_unknown_token(self):
        svc = GovernanceTokenService(signing_key="test-key")
        self.assertIsNone(svc.verify("govt.bogus"))
        self.assertFalse(svc.revoke("govt.bogus"))

    def test_issued_count(self):
        svc = GovernanceTokenService(signing_key="test-key")
        svc.issue(TokenRequest(agent_id="a1"))
        svc.issue(TokenRequest(agent_id="a2"))
        self.assertEqual(svc.issued_count(), 2)

    def test_token_valid_property(self):
        svc = GovernanceTokenService(signing_key="test-key")
        token = svc.issue(TokenRequest(agent_id="a1", ttl_seconds=60.0))
        self.assertTrue(token.valid)
        svc.revoke(token.token_value)
        self.assertFalse(token.valid)


if __name__ == "__main__":
    unittest.main()