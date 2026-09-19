"""Tests for KillSwitch and QuarantineFlag (commit 4: kill-switch)."""

import os
import sys
import types
import unittest
from types import SimpleNamespace

sys.modules["grpc"] = types.ModuleType("grpc")
sys.modules["grpc.aio"] = types.ModuleType("grpc.aio")
sys.modules["google.protobuf"] = types.ModuleType("google.protobuf")

from thinkbox.agent.control_plane.killswitch import KillSwitch, QuarantineFlag, KillSignal


class TestKillSwitch(unittest.TestCase):

    def test_no_kill_by_default(self):
        ks = KillSwitch()
        signal = ks.check()
        self.assertFalse(signal.triggered)

    def test_env_kill(self):
        os.environ["THINKBOX_KILL_AGENT_TEST1"] = "1"
        try:
            ks = KillSwitch(env_var="THINKBOX_KILL_AGENT_TEST1")
            signal = ks.check()
            self.assertTrue(signal.triggered)
            self.assertIn("THINKBOX_KILL_AGENT_TEST1", signal.reason)
        finally:
            del os.environ["THINKBOX_KILL_AGENT_TEST1"]

    def test_quarantine_kill(self):
        ks = KillSwitch()
        ks.set_quarantine("test quarantine")
        signal = ks.check()
        self.assertTrue(signal.triggered)
        self.assertIn("quarantine", signal.reason)

    def test_clear_quarantine(self):
        ks = KillSwitch()
        ks.set_quarantine("test")
        ks.clear_quarantine()
        signal = ks.check()
        self.assertFalse(signal.triggered)

    def test_signal_timestamp(self):
        import time
        os.environ["THINKBOX_KILL_AGENT_TEST2"] = "1"
        try:
            ks = KillSwitch(env_var="THINKBOX_KILL_AGENT_TEST2")
            signal = ks.check()
            self.assertGreater(signal.timestamp, 0)
        finally:
            del os.environ["THINKBOX_KILL_AGENT_TEST2"]


class TestQuarantineFlag(unittest.TestCase):

    def test_not_quarantined_by_default(self):
        qf = QuarantineFlag()
        self.assertFalse(qf.active)
        self.assertEqual(qf.reason, "")

    def test_set_quarantine(self):
        qf = QuarantineFlag()
        qf.quarantine("unsafe")
        self.assertTrue(qf.active)
        self.assertEqual(qf.reason, "unsafe")

    def test_clear_quarantine(self):
        qf = QuarantineFlag()
        qf.quarantine("unsafe")
        qf.clear()
        self.assertFalse(qf.active)
        self.assertEqual(qf.reason, "")


if __name__ == "__main__":
    unittest.main()
