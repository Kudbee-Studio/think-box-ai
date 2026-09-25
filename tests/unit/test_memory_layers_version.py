"""Hermetic tests for organizational versioning and snapshots (PR #205)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.memory.schema import MemoryLayer
from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    export_snapshot,
    import_snapshot,
    org_history,
    read_organizational,
    read_session,
    write_organizational,
    write_session,
    write_task,
    write_verified,
)


class TestMemoryOrgVersionSnapshot(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "layers.db")

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def test_org_write_is_version_one(self) -> None:
        entry = write_organizational(
            self.store,
            {"pattern_id": "four", "description": "layers", "evidence": ["AGENTS.md"]},
        )
        self.assertEqual(entry.value["version"], 1)
        self.assertEqual(read_organizational(self.store, "four").value["description"], "layers")

    def test_org_rewrite_archives_previous(self) -> None:
        write_organizational(
            self.store,
            {"pattern_id": "four", "description": "v1 text", "evidence": ["AGENTS.md"]},
        )
        write_organizational(
            self.store,
            {
                "pattern_id": "four",
                "description": "v2 text",
                "evidence": ["AGENTS.md", "docs/architecture-v1.md"],
            },
        )
        current = read_organizational(self.store, "four")
        self.assertEqual(current.value["version"], 2)
        self.assertEqual(current.value["description"], "v2 text")
        history = org_history(self.store, "four")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].key, "org:pattern:four:v1")
        self.assertEqual(history[0].value["description"], "v1 text")
        self.assertEqual(history[-1].key, "org:pattern:four")

    def test_identical_org_write_does_not_version(self) -> None:
        first = write_organizational(
            self.store,
            {"pattern_id": "same", "description": "stable", "evidence": ["AGENTS.md"]},
        )
        second = write_organizational(
            self.store,
            {"pattern_id": "same", "description": "stable", "evidence": ["AGENTS.md"]},
        )
        self.assertEqual(first.key, second.key)
        self.assertEqual(self.store.count(MemoryLayer.ORGANIZATIONAL), 1)
        self.assertEqual(len(org_history(self.store, "same")), 1)

    def test_org_history_missing(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            org_history(self.store, "gone")
        self.assertEqual(err.exception.code, "missing_org")

    def test_export_import_round_trip(self) -> None:
        write_session(self.store, {"session_id": "s1", "goal": "snap"})
        write_task(self.store, {"task_id": "t1", "status": "running"})
        write_organizational(
            self.store,
            {"pattern_id": "four", "description": "layers", "evidence": ["AGENTS.md"]},
        )
        write_verified(self.store, {"id": "f1", "fact": "catalog", "how": "walk"})
        blob = export_snapshot(self.store)
        self.assertFalse(blob["live_verified"])
        self.assertIn("exported_at", blob)
        other = MemoryStore(Path(self.tmp.name) / "copy.db")
        try:
            result = import_snapshot(other, blob)
            self.assertFalse(result["live_verified"])
            self.assertEqual(read_session(other, "s1").value["goal"], "snap")
            self.assertEqual(read_organizational(other, "four").value["description"], "layers")
            self.assertGreaterEqual(result["verified_knowledge"], 1)
        finally:
            other.close()

    def test_import_rejects_live_claim(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            import_snapshot(self.store, {"layers": {}, "live_verified": True})
        self.assertEqual(err.exception.code, "live_claim")

    def test_import_rejects_invalid_shape(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            import_snapshot(self.store, {"layers": "nope"})
        self.assertEqual(err.exception.code, "invalid_snapshot")

    def test_export_import_keeps_org_history(self) -> None:
        write_organizational(
            self.store,
            {"pattern_id": "four", "description": "v1", "evidence": ["AGENTS.md"]},
        )
        write_organizational(
            self.store,
            {"pattern_id": "four", "description": "v2", "evidence": ["AGENTS.md"]},
        )
        blob = export_snapshot(self.store)
        other = MemoryStore(Path(self.tmp.name) / "hist.db")
        try:
            import_snapshot(other, blob)
            history = org_history(other, "four")
            self.assertGreaterEqual(len(history), 2)
            self.assertEqual(history[-1].value["description"], "v2")
        finally:
            other.close()


if __name__ == "__main__":
    unittest.main()
