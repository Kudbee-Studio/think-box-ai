"""Unit tests for thinkbox/handoff.py — Think Box substrate handoff."""

import unittest
from thinkbox.handoff import ThinkBoxHandoff
from thinkbox.workspace import WorkspaceRegistry


class TestThinkBoxHandoff(unittest.TestCase):
    def test_handoff_changes_substrate(self):
        registry = WorkspaceRegistry()
        box = registry.create(owner_id="a1", substrate="local")
        handoff = ThinkBoxHandoff()
        record = handoff.handoff(box, to_substrate="container")
        self.assertEqual(box.substrate, "container")
        self.assertEqual(record.from_substrate, "local")
        self.assertEqual(record.to_substrate, "container")

    def test_integrity_verification(self):
        registry = WorkspaceRegistry()
        box = registry.create(owner_id="a1", state={"data": "x"})
        handoff = ThinkBoxHandoff()
        record = handoff.handoff(box, "cloud_gpu")
        self.assertTrue(handoff.verify_integrity(box, record))

    def test_integrity_fails_on_mutation(self):
        registry = WorkspaceRegistry()
        box = registry.create(owner_id="a1", state={"data": "x"})
        handoff = ThinkBoxHandoff()
        record = handoff.handoff(box, "cloud_gpu")
        box.state["data"] = "corrupted"
        self.assertFalse(handoff.verify_integrity(box, record))

    def test_history_filtered_by_box(self):
        registry = WorkspaceRegistry()
        box_a = registry.create(owner_id="a1")
        box_b = registry.create(owner_id="a2")
        handoff = ThinkBoxHandoff()
        handoff.handoff(box_a, "container")
        handoff.handoff(box_b, "container")
        history = handoff.history(box_id=box_a.box_id)
        self.assertEqual(len(history), 1)


if __name__ == "__main__":
    unittest.main()