"""Tests for ChaosHooks (commit 9: chaos fault hooks OFF by default)."""

import sys
import types
import unittest
from types import SimpleNamespace

sys.modules["grpc"] = types.ModuleType("grpc")
sys.modules["grpc.aio"] = types.ModuleType("grpc.aio")
sys.modules["google.protobuf"] = types.ModuleType("google.protobuf")

from thinkbox.agent.control_plane.chaos import ChaosHooks, ChaosConfig, FaultType


class TestChaosHooks(unittest.TestCase):

    def test_off_by_default(self):
        ch = ChaosHooks()
        self.assertFalse(ch.config.enabled)
        self.assertIsNone(ch.should_fault("any"))

    def test_enable_deny(self):
        ch = ChaosHooks()
        ch.enable(ChaosConfig(enabled=True, fault_type=FaultType.DENY, deny_probability=1.0))
        result = ch.should_fault("capacity_request")
        self.assertEqual(result, "DENY")

    def test_disable_no_fault(self):
        ch = ChaosHooks()
        ch.enable(ChaosConfig(enabled=True, fault_type=FaultType.DENY, deny_probability=1.0))
        ch.disable()
        self.assertFalse(ch.config.enabled)
        self.assertIsNone(ch.should_fault("any"))

    def test_inject_fault(self):
        ch = ChaosHooks()
        ch.enable()
        ch.inject("capacity_request", "DENY")
        result = ch.should_fault("capacity_request")
        self.assertEqual(result, "DENY")
        # Other actions not affected
        self.assertIsNone(ch.should_fault("secret_inject"))

    def test_clear_injected(self):
        ch = ChaosHooks()
        ch.enable()
        ch.inject("x", "DENY")
        ch.clear_injected()
        self.assertEqual(ch.active_faults, {})

    def test_timeout_fault(self):
        ch = ChaosHooks()
        ch.enable(ChaosConfig(enabled=True, fault_type=FaultType.TIMEOUT, deny_probability=1.0))
        result = ch.should_fault("config_watch")
        self.assertEqual(result, "TIMEOUT")


if __name__ == "__main__":
    unittest.main()
