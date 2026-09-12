"""Unit tests for thinkbox/identity.py — KUDBEE identity ledger."""

import unittest
from thinkbox.identity import IdentityLedger


class TestIdentityLedger(unittest.TestCase):
    def test_register_assigns_id(self):
        ledger = IdentityLedger()
        identity = ledger.register(capabilities=["memory:read"])
        self.assertTrue(identity.agent_id.startswith("agent_"))

    def test_has_capability(self):
        ledger = IdentityLedger()
        identity = ledger.register(capabilities=["file:read", "net:http"])
        self.assertTrue(ledger.has_capability(identity.agent_id, "file:read"))
        self.assertFalse(ledger.has_capability(identity.agent_id, "file:write"))

    def test_revoked_denies_all(self):
        ledger = IdentityLedger()
        identity = ledger.register(capabilities=["file:read"])
        ledger.revoke(identity.agent_id)
        self.assertFalse(ledger.has_capability(identity.agent_id, "file:read"))

    def test_unknown_agent(self):
        ledger = IdentityLedger()
        self.assertIsNone(ledger.get("missing"))
        self.assertFalse(ledger.has_capability("missing", "file:read"))
        self.assertFalse(ledger.grant("missing", "x"))

    def test_list(self):
        ledger = IdentityLedger()
        ledger.register(agent_id="a1", capabilities=["x"])
        ledger.register(agent_id="a2")
        self.assertEqual(len(ledger.list()), 2)


if __name__ == "__main__":
    unittest.main()