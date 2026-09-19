"""Tests for EvidenceTelemetry (commit 8: evidence-labeled telemetry)."""

import sys
import types
import unittest
from types import SimpleNamespace

sys.modules["grpc"] = types.ModuleType("grpc")
sys.modules["grpc.aio"] = types.ModuleType("grpc.aio")
sys.modules["google.protobuf"] = types.ModuleType("google.protobuf")

from thinkbox.agent.control_plane.evidence_telemetry import (
    EvidenceTelemetry, EvidenceEvent, EvidenceLabel,
)


class TestEvidenceTelemetry(unittest.TestCase):

    def test_default_label_simulated(self):
        et = EvidenceTelemetry()
        evt = et.emit("test", agent_id="a1")
        self.assertEqual(evt.label, EvidenceLabel.SIMULATED)

    def test_emit_measured(self):
        et = EvidenceTelemetry()
        evt = et.emit("test", label=EvidenceLabel.MEASURED, agent_id="a1")
        self.assertEqual(evt.label, EvidenceLabel.MEASURED)

    def test_emit_lifecycle(self):
        et = EvidenceTelemetry()
        evt = et.emit_lifecycle("IDLE", "EXECUTING", agent_id="a1")
        self.assertIn("lifecycle", evt.event_type)
        self.assertEqual(evt.data["from"], "IDLE")
        self.assertEqual(evt.data["to"], "EXECUTING")

    def test_events_by_label(self):
        et = EvidenceTelemetry()
        et.emit("a", label=EvidenceLabel.SIMULATED)
        et.emit("b", label=EvidenceLabel.MEASURED)
        et.emit("c", label=EvidenceLabel.SIMULATED)
        sim = et.events_by_label(EvidenceLabel.SIMULATED)
        self.assertEqual(len(sim), 2)

    def test_measured_count(self):
        et = EvidenceTelemetry()
        et.emit("a", label=EvidenceLabel.MEASURED)
        et.emit("b", label=EvidenceLabel.SIMULATED)
        et.emit("c", label=EvidenceLabel.MEASURED)
        self.assertEqual(et.measured_count(), 2)

    def test_clear(self):
        et = EvidenceTelemetry()
        et.emit("a")
        et.clear()
        self.assertEqual(len(et.events()), 0)

    def test_emit_timestamp_set(self):
        import time
        et = EvidenceTelemetry()
        before = time.time()
        evt = et.emit("test")
        after = time.time()
        self.assertGreaterEqual(evt.timestamp, before)
        self.assertLessEqual(evt.timestamp, after)


if __name__ == "__main__":
    unittest.main()
