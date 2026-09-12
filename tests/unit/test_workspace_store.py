"""Unit tests for WorkspaceStore — SQLite Think Box persistence."""

import tempfile
import unittest
from pathlib import Path

from thinkbox.workspace import WorkspaceRegistry, WorkspaceStore


class TestWorkspaceStore(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.store = WorkspaceStore(Path(self._tmp.name) / "boxes.db")

    def tearDown(self) -> None:
        self.store.close()
        self._tmp.cleanup()

    def test_save_and_load_roundtrip(self):
        registry = WorkspaceRegistry()
        box = registry.create(owner_id="a1", capabilities=["net:http"], state={"x": 1})
        self.store.save(box)
        loaded = self.store.load(box.box_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.owner_id, "a1")
        self.assertIn("net:http", loaded.capabilities)
        self.assertEqual(loaded.state["x"], 1)

    def test_load_missing_returns_none(self):
        self.assertIsNone(self.store.load("box_missing"))

    def test_load_by_owner(self):
        registry = WorkspaceRegistry()
        b1 = registry.create(owner_id="a1")
        b2 = registry.create(owner_id="a1")
        self.store.save(b1)
        self.store.save(b2)
        boxes = self.store.load_by_owner("a1")
        self.assertEqual(len(boxes), 2)

    def test_delete(self):
        registry = WorkspaceRegistry()
        box = registry.create(owner_id="a1")
        self.store.save(box)
        self.assertTrue(self.store.delete(box.box_id))
        self.assertIsNone(self.store.load(box.box_id))
        self.assertFalse(self.store.delete(box.box_id))

    def test_restore_preserves_version(self):
        registry = WorkspaceRegistry()
        box = registry.create(owner_id="a1", substrate="container")
        registry.touch(box.box_id)
        self.assertEqual(box.version, 2)
        self.store.save(box)
        loaded = self.store.load(box.box_id)
        self.assertEqual(loaded.version, 2)
        self.assertEqual(loaded.substrate, "container")


if __name__ == "__main__":
    unittest.main()