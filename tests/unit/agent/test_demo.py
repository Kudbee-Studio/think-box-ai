"""Tests for Demo (commit 10: demo-in-60s)."""

import sys
import types
import unittest
from types import SimpleNamespace

sys.modules["grpc"] = types.ModuleType("grpc")
sys.modules["grpc.aio"] = types.ModuleType("grpc.aio")
sys.modules["google.protobuf"] = types.ModuleType("google.protobuf")
sys.modules["thinkbox.agent.protocol"] = types.ModuleType("protocol")
sys.modules["thinkbox.agent.protocol"].governance_pb2 = types.ModuleType("governance_pb2")
sys.modules["thinkbox.agent.protocol"].governance_pb2_grpc = types.ModuleType("governance_pb2_grpc")
sys.modules["thinkbox.agent.protocol"].orchestration_pb2 = types.ModuleType("orchestration_pb2")
sys.modules["thinkbox.agent.protocol"].orchestration_pb2_grpc = types.ModuleType("orchestration_pb2_grpc")

# Import demo module to verify it loads without error
from thinkbox.agent.control_plane import demo as demo_module


class TestDemo(unittest.TestCase):

    def test_demo_imports(self):
        self.assertTrue(hasattr(demo_module, "demo"))

    def test_demo_runs(self):
        """Demo should run without exception."""
        try:
            demo_module.demo()
        except Exception as e:
            self.fail(f"demo() raised {e}")


if __name__ == "__main__":
    unittest.main()
