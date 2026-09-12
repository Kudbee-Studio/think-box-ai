"""Unit tests for thinkbox/workspace.py — Think Box workspaces."""

import unittest
from thinkbox.workspace import WorkspaceRegistry


class TestWorkspaceRegistry(unittest.TestCase):
    def test_create_sets_bindings(self):
        registry = WorkspaceRegistry()
        box = registry.create(owner_id="a1", capabilities=["file:read"], policy_version="2")
        self.assertTrue(box.box_id.startswith("box_"))
        self.assertEqual(box.owner_id, "a1")
        self.assertIn("file:read", box.capabilities)
        self.assertEqual(box.policy_version, "2")

    def test_get_and_list(self):
        registry = WorkspaceRegistry()
        box = registry.create(owner_id="a1")
        self.assertIs(registry.get(box.box_id), box)
        self.assertEqual(len(registry.list()), 1)

    def test_get_by_owner(self):
        registry = WorkspaceRegistry()
        registry.create(owner_id="a1")
        registry.create(owner_id="a1")
        registry.create(owner_id="a2")
        self.assertEqual(len(registry.get_by_owner("a1")), 2)

    def test_touch_bumps_version(self):
        registry = WorkspaceRegistry()
        box = registry.create(owner_id="a1")
        before = box.version
        self.assertTrue(registry.touch(box.box_id))
        self.assertEqual(box.version, before + 1)

    def test_touch_missing(self):
        registry = WorkspaceRegistry()
        self.assertFalse(registry.touch("box_missing"))

    def test_snapshot_contains_bindings(self):
        registry = WorkspaceRegistry()
        box = registry.create(owner_id="a1", substrate="container", state={"progress": 0.5})
        snap = box.snapshot()
        self.assertEqual(snap["substrate"], "container")
        self.assertEqual(snap["state"]["progress"], 0.5)


if __name__ == "__main__":
    unittest.main()