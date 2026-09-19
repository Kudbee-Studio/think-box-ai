"""Tests for ControlPlaneAdmission (commit 1: fail-closed admission)."""

import asyncio
import sys
import types
import unittest
import unittest.mock
from types import SimpleNamespace

sys.modules["grpc"] = types.ModuleType("grpc")
sys.modules["grpc.aio"] = types.ModuleType("grpc.aio")
sys.modules["google.protobuf"] = types.ModuleType("google.protobuf")
sys.modules["google.protobuf.struct_pb2"] = types.ModuleType("struct_pb2")
sys.modules["thinkbox.agent.protocol"] = types.ModuleType("protocol")
sys.modules["thinkbox.agent.protocol"].governance_pb2 = types.ModuleType("governance_pb2")
sys.modules["thinkbox.agent.protocol"].governance_pb2_grpc = types.ModuleType("governance_pb2_grpc")
sys.modules["thinkbox.agent.protocol"].orchestration_pb2 = types.ModuleType("orchestration_pb2")
sys.modules["thinkbox.agent.protocol"].orchestration_pb2_grpc = types.ModuleType("orchestration_pb2_grpc")

from thinkbox.agent.control_plane.admission import ControlPlaneAdmission, AdmissionResult


class TestAdmissionFailClosed(unittest.TestCase):

    def _make_mock_gov(self, allowed=True, reason=""):
        gov = SimpleNamespace(check_admission=unittest.mock.AsyncMock())
        gov.check_admission.return_value = SimpleNamespace(
            allowed=allowed, reason=reason, conditions={},
        )
        return gov

    def test_admit_allowed(self):
        gov = self._make_mock_gov(allowed=True)
        admission = ControlPlaneAdmission(gov)
        result = asyncio.run(admission.admit("AGENT_SPAWN", {"agent_type": "TASK_AGENT"}))
        self.assertTrue(result.allowed)
        self.assertEqual(result.action_type, "AGENT_SPAWN")

    def test_admit_denied(self):
        gov = self._make_mock_gov(allowed=False, reason="quota exceeded")
        admission = ControlPlaneAdmission(gov)
        result = asyncio.run(admission.admit("AGENT_SPAWN", {"agent_type": "TASK_AGENT"}))
        self.assertFalse(result.allowed)
        self.assertIn("quota exceeded", result.reason)

    def test_admit_gov_exception_is_fail_closed(self):
        gov = SimpleNamespace(check_admission=unittest.mock.AsyncMock(side_effect=RuntimeError("boom")))
        admission = ControlPlaneAdmission(gov)
        result = asyncio.run(admission.admit("AGENT_SPAWN", {}))
        self.assertFalse(result.allowed)
        self.assertIn("boom", result.reason)

    def test_last_decision_tracking(self):
        gov = self._make_mock_gov(allowed=True)
        admission = ControlPlaneAdmission(gov)
        asyncio.run(admission.admit("TASK_EXECUTE", {"task_id": "t1"}))
        self.assertIsNotNone(admission.last_decision)
        self.assertTrue(admission.last_decision.allowed)

    def test_must_admit_true_after_admission(self):
        gov = self._make_mock_gov(allowed=True)
        admission = ControlPlaneAdmission(gov)
        asyncio.run(admission.admit("TASK_EXECUTE", {}))
        self.assertTrue(admission.must_admit("TASK_EXECUTE", {}))

    def test_must_admit_false_before_admission(self):
        gov = self._make_mock_gov(allowed=True)
        admission = ControlPlaneAdmission(gov)
        self.assertFalse(admission.must_admit("TASK_EXECUTE", {}))


if __name__ == "__main__":
    unittest.main()
