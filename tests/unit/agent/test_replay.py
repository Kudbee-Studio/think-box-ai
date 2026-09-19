"""Tests for ReplayEnvelope (commit 5: deterministic replay)."""

import sys
import types
import unittest
from types import SimpleNamespace

sys.modules["grpc"] = types.ModuleType("grpc")
sys.modules["grpc.aio"] = types.ModuleType("grpc.aio")
sys.modules["google.protobuf"] = types.ModuleType("google.protobuf")

from thinkbox.agent.control_plane.replay import ReplayEnvelope, ReplayEvent


class TestReplayEnvelope(unittest.TestCase):

    def test_empty_envelope(self):
        env = ReplayEnvelope(agent_id="a1")
        self.assertEqual(env.size(), 0)
        self.assertEqual(len(env.events_for_action("X")), 0)

    def test_add_input(self):
        env = ReplayEnvelope(agent_id="a1")
        env.add_input("CAPACITY", {"cpu": 2})
        self.assertEqual(env.size(), 1)
        ev = env.events[0]
        self.assertEqual(ev.phase, "INPUT")
        self.assertEqual(ev.action_type, "CAPACITY")

    def test_add_receipt(self):
        env = ReplayEnvelope(agent_id="a1")
        env.add_receipt("SECRET", {"handles": ["h1"]})
        self.assertEqual(env.size(), 1)
        ev = env.events[0]
        self.assertEqual(ev.phase, "RECEIPT")

    def test_events_for_action(self):
        env = ReplayEnvelope(agent_id="a1")
        env.add_input("A", {})
        env.add_receipt("A", {})
        env.add_input("B", {})
        a_events = env.events_for_action("A")
        self.assertEqual(len(a_events), 2)
        self.assertEqual(a_events[0].phase, "INPUT")
        self.assertEqual(a_events[1].phase, "RECEIPT")

    def test_json_roundtrip(self):
        env = ReplayEnvelope(agent_id="a1", metadata={"v": 1})
        env.add_input("CAPACITY", {"cpu": 2})
        env.add_receipt("CAPACITY", {"granted": True})
        s = env.to_json()
        restored = ReplayEnvelope.from_json(s)
        self.assertEqual(restored.agent_id, "a1")
        self.assertEqual(restored.size(), 2)
        self.assertEqual(restored.events[0].phase, "INPUT")
        self.assertEqual(restored.events[1].data["granted"], True)

    def test_to_json_deterministic(self):
        env = ReplayEnvelope(agent_id="a1")
        env.add_input("X", {"b": 1, "a": 2})
        s1 = env.to_json()
        env2 = ReplayEnvelope(agent_id="a1")
        env2.add_input("X", {"b": 1, "a": 2})
        s2 = env2.to_json()
        self.assertEqual(s1, s2)


if __name__ == "__main__":
    unittest.main()
