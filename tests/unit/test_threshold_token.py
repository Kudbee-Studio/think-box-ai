"""Unit tests for thinkbox/governance/distributed/token — Threshold-signed Governance Tokens."""

import unittest

from thinkbox.governance.distributed.token import (
    ThresholdGovernanceToken,
    ThresholdGovernanceTokenService,
    ThresholdTokenRequest,
    ValidatorSignature,
)


class TestThresholdGovernanceToken(unittest.TestCase):
    def _make_token(self, **kwargs):
        defaults = dict(
            token_value="test_token",
            agent_id="agent_1",
            capabilities=["file:read"],
            policy_version="1",
            issued_at=1000000000.0,
            expires_at=2000000000.0,
            validator_signatures=[],
            threshold=2,
            validators=["v1", "v2"],
            revoked=False,
        )
        defaults.update(kwargs)
        return ThresholdGovernanceToken(**defaults)

    def test_valid_when_fully_signed(self):
        token = self._make_token(
            validator_signatures=[
                ValidatorSignature("v1", "test_token", "sig1"),
                ValidatorSignature("v2", "test_token", "sig2"),
            ],
        )
        self.assertTrue(token.is_fully_signed())
        self.assertTrue(token.valid)

    def test_invalid_when_not_fully_signed(self):
        token = self._make_token(
            validator_signatures=[
                ValidatorSignature("v1", "test_token", "sig1"),
            ],
        )
        self.assertFalse(token.is_fully_signed())
        self.assertFalse(token.valid)

    def test_invalid_when_revoked(self):
        token = self._make_token(revoked=True)
        self.assertFalse(token.valid)

    def test_invalid_when_expired(self):
        token = self._make_token(expires_at=100.0, issued_at=50.0)
        self.assertTrue(token.is_expired(now=200.0))
        self.assertFalse(token.valid)

    def test_valid_at_boundary(self):
        token = self._make_token(expires_at=200.0, issued_at=100.0)
        self.assertFalse(token.is_expired(now=199.9))
        self.assertTrue(token.is_expired(now=200.1))


class TestThresholdGovernanceTokenService(unittest.TestCase):
    def setUp(self):
        self.service = ThresholdGovernanceTokenService(
            signing_key="test-key",
            validator_ids=["v1", "v2", "v3"],
            threshold=2,
        )

    def test_issue_token(self):
        request = ThresholdTokenRequest(
            agent_id="agent_1",
            capabilities=["file:read", "file:write"],
            threshold=2,
            validator_ids=["v1", "v2"],
        )
        token = self.service.issue(request)
        self.assertIsInstance(token, ThresholdGovernanceToken)
        self.assertEqual(token.agent_id, "agent_1")
        self.assertEqual(token.threshold, 2)
        self.assertEqual(token.validators, ["v1", "v2"])
        self.assertFalse(token.valid)

    def test_issue_without_validator_ids(self):
        service = ThresholdGovernanceTokenService(
            signing_key="test-key",
            validator_ids=["v1", "v2"],
            threshold=2,
        )
        request = ThresholdTokenRequest(agent_id="agent_1", threshold=2)
        token = service.issue(request)
        self.assertEqual(token.validators, ["v1", "v2"])

    def test_sign_by_validator(self):
        request = ThresholdTokenRequest(
            agent_id="agent_1",
            capabilities=["file:read"],
            threshold=2,
            validator_ids=["v1", "v2"],
        )
        token = self.service.issue(request)
        result = self.service.sign(token.token_value, "v1")
        self.assertTrue(result)
        result2 = self.service.sign(token.token_value, "v2")
        self.assertTrue(result2)
        verified = self.service.verify(token.token_value)
        self.assertIsNotNone(verified)
        self.assertTrue(verified.valid)

    def test_sign_by_unauthorized_validator(self):
        request = ThresholdTokenRequest(
            agent_id="agent_1",
            capabilities=["file:read"],
            threshold=2,
            validator_ids=["v1", "v2"],
        )
        token = self.service.issue(request)
        result = self.service.sign(token.token_value, "v3")
        self.assertFalse(result)

    def test_duplicate_sign_rejected(self):
        request = ThresholdTokenRequest(
            agent_id="agent_1",
            capabilities=["file:read"],
            threshold=2,
            validator_ids=["v1", "v2"],
        )
        token = self.service.issue(request)
        self.assertTrue(self.service.sign(token.token_value, "v1"))
        self.assertFalse(self.service.sign(token.token_value, "v1"))

    def test_verify_unsign_token(self):
        request = ThresholdTokenRequest(
            agent_id="agent_1",
            capabilities=["file:read"],
            threshold=2,
            validator_ids=["v1", "v2"],
        )
        token = self.service.issue(request)
        verified = self.service.verify(token.token_value)
        self.assertIsNone(verified)

    def test_verify_unknown_token(self):
        verified = self.service.verify("nonexistent")
        self.assertIsNone(verified)

    def test_revoke(self):
        request = ThresholdTokenRequest(
            agent_id="agent_1",
            capabilities=["file:read"],
            threshold=2,
            validator_ids=["v1", "v2"],
        )
        token = self.service.issue(request)
        self.service.sign(token.token_value, "v1")
        self.service.sign(token.token_value, "v2")
        self.assertTrue(self.service.revoke(token.token_value))
        verified = self.service.verify(token.token_value)
        self.assertIsNone(verified)

    def test_revoke_unknown_token(self):
        self.assertFalse(self.service.revoke("nonexistent"))

    def test_revoke_for_agent(self):
        request1 = ThresholdTokenRequest(
            agent_id="agent_1",
            capabilities=["file:read"],
            threshold=2,
            validator_ids=["v1", "v2"],
        )
        request2 = ThresholdTokenRequest(
            agent_id="agent_2",
            capabilities=["file:write"],
            threshold=2,
            validator_ids=["v1", "v2"],
        )
        self.service.issue(request1)
        self.service.issue(request2)
        count = self.service.revoke_for_agent("agent_1")
        self.assertEqual(count, 1)

    def test_pending_count(self):
        request = ThresholdTokenRequest(
            agent_id="agent_1",
            capabilities=["file:read"],
            threshold=2,
            validator_ids=["v1", "v2"],
        )
        token = self.service.issue(request)
        self.assertEqual(self.service.pending_count(), 1)
        self.service.sign(token.token_value, "v1")
        self.service.sign(token.token_value, "v2")
        self.assertEqual(self.service.pending_count(), 0)

    def test_signed_count(self):
        request1 = ThresholdTokenRequest(
            agent_id="agent_1",
            capabilities=["file:read"],
            threshold=2,
            validator_ids=["v1", "v2"],
        )
        request2 = ThresholdTokenRequest(
            agent_id="agent_2",
            capabilities=["file:write"],
            threshold=2,
            validator_ids=["v1", "v2"],
        )
        t1 = self.service.issue(request1)
        t2 = self.service.issue(request2)
        self.assertEqual(self.service.signed_count(), 0)
        self.service.sign(t1.token_value, "v1")
        self.service.sign(t1.token_value, "v2")
        self.assertEqual(self.service.signed_count(), 1)
        self.service.sign(t2.token_value, "v1")
        self.service.sign(t2.token_value, "v2")
        self.assertEqual(self.service.signed_count(), 2)

    def test_validators_property(self):
        self.assertEqual(self.service.validators, ["v1", "v2", "v3"])

    def test_threshold_property(self):
        self.assertEqual(self.service.threshold, 2)

    def test_validator_signatures_for(self):
        request = ThresholdTokenRequest(
            agent_id="agent_1",
            capabilities=["file:read"],
            threshold=2,
            validator_ids=["v1", "v2"],
        )
        token = self.service.issue(request)
        self.service.sign(token.token_value, "v1")
        sigs = self.service.validator_signatures_for(token.token_value)
        self.assertEqual(len(sigs), 1)
        self.assertEqual(sigs[0].validator_id, "v1")

    def test_issued_count_inherited(self):
        request = ThresholdTokenRequest(
            agent_id="agent_1",
            capabilities=["file:read"],
            threshold=2,
            validator_ids=["v1", "v2"],
        )
        self.service.issue(request)
        self.assertEqual(self.service.issued_count(), 1)
