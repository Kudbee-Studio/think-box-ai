"""Hermetic tests for memory-layer read, query, and retention (PR #204)."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.memory.schema import MemoryEntry, MemoryEntryType, MemoryLayer
from core.memory.store import MemoryStore
from thinkbox.memory_layers import (
    MemoryLayerError,
    apply_retention,
    delete_organizational,
    delete_verified,
    effective_confidence,
    end_session,
    end_task,
    query_layer,
    read_organizational,
    read_session,
    read_task,
    read_verified,
    record_task_step,
    write_organizational,
    write_session,
    write_task,
    write_verified,
)


class TestMemoryLayerQueryRetention(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = MemoryStore(Path(self.tmp.name) / "layers.db")

    def tearDown(self) -> None:
        self.store.close()
        self.tmp.cleanup()

    def test_read_each_layer(self) -> None:
        write_session(self.store, {"session_id": "s1", "goal": "read"})
        write_task(self.store, {"task_id": "t1", "status": "running"})
        write_organizational(
            self.store,
            {"pattern_id": "four", "description": "layers", "evidence": ["AGENTS.md"]},
        )
        write_verified(
            self.store,
            {"id": "f1", "fact": "catalog", "how": "walk", "confidence": 1.0},
        )
        self.assertEqual(read_session(self.store, "s1").value["goal"], "read")
        self.assertEqual(read_task(self.store, "t1").value["status"], "running")
        self.assertEqual(read_organizational(self.store, "four").value["pattern_id"], "four")
        viewed = read_verified(self.store, "f1")
        self.assertEqual(viewed["fact"], "catalog")
        self.assertFalse(viewed["live_verified"])
        self.assertAlmostEqual(viewed["stored_confidence"], 1.0)
        self.assertLessEqual(viewed["effective_confidence"], 1.0)

    def test_read_missing_is_fail_closed(self) -> None:
        with self.assertRaises(MemoryLayerError) as err:
            read_session(self.store, "gone")
        self.assertEqual(err.exception.code, "missing_session")
        with self.assertRaises(MemoryLayerError) as err2:
            read_verified(self.store, "gone")
        self.assertEqual(err2.exception.code, "missing_verified")

    def test_query_layer_prefix(self) -> None:
        write_task(self.store, {"task_id": "keep", "status": "running"})
        record_task_step(self.store, "keep", "ingest", {"ok": True})
        write_task(self.store, {"task_id": "other", "status": "running"})
        rows = query_layer(self.store, MemoryLayer.TASK, prefix="task:keep")
        keys = sorted(row.key for row in rows)
        self.assertEqual(keys, ["task:keep", "task:keep:step:ingest"])

    def test_end_session_leaves_org_and_verified(self) -> None:
        write_session(self.store, {"session_id": "s1"})
        write_organizational(
            self.store,
            {"pattern_id": "keep", "description": "stay", "evidence": ["docs/STATUS.md"]},
        )
        write_verified(self.store, {"id": "keep", "fact": "stay", "how": "unit"})
        end_session(self.store, "s1")
        with self.assertRaises(MemoryLayerError):
            read_session(self.store, "s1")
        self.assertEqual(self.store.count(MemoryLayer.ORGANIZATIONAL), 1)
        self.assertEqual(self.store.count(MemoryLayer.VERIFIED_KNOWLEDGE), 1)

    def test_end_task_deletes_steps(self) -> None:
        write_task(self.store, {"task_id": "t1", "status": "running"})
        record_task_step(self.store, "t1", "ingest", {"ok": True})
        result = end_task(self.store, "t1")
        self.assertIn("task:t1", result["deleted"])
        self.assertIn("task:t1:step:ingest", result["deleted"])
        self.assertEqual(self.store.count(MemoryLayer.TASK), 0)

    def test_org_and_verified_refuse_delete(self) -> None:
        write_organizational(
            self.store,
            {"pattern_id": "keep", "description": "stay", "evidence": ["AGENTS.md"]},
        )
        write_verified(self.store, {"id": "keep", "fact": "stay", "how": "unit"})
        with self.assertRaises(MemoryLayerError) as err:
            delete_organizational(self.store, "keep")
        self.assertEqual(err.exception.code, "append_only")
        with self.assertRaises(MemoryLayerError) as err2:
            delete_verified(self.store, "keep")
        self.assertEqual(err2.exception.code, "no_delete")
        self.assertEqual(self.store.count(MemoryLayer.ORGANIZATIONAL), 1)
        self.assertEqual(self.store.count(MemoryLayer.VERIFIED_KNOWLEDGE), 1)

    def test_verified_confidence_decays(self) -> None:
        write_verified(
            self.store,
            {"id": "old", "fact": "was true", "how": "unit", "confidence": 1.0},
        )
        entry = self.store.get("verified:old")
        stale = MemoryEntry(
            key=entry.key,
            layer=entry.layer,
            entry_type=entry.entry_type,
            value=entry.value,
            created_at=(datetime.now(timezone.utc) - timedelta(hours=168)).isoformat(),
            confidence=1.0,
        )
        self.assertAlmostEqual(effective_confidence(stale, half_life_hours=168.0), 0.5, places=5)
        with self.assertRaises(MemoryLayerError) as err:
            effective_confidence(stale, half_life_hours=0)
        self.assertEqual(err.exception.code, "invalid_half_life")

    def test_retention_expires_old_session_and_ended_task(self) -> None:
        write_session(self.store, {"session_id": "fresh"})
        write_task(self.store, {"task_id": "done", "status": "ended"})
        record_task_step(self.store, "done", "wrap", {"ok": True})
        write_task(self.store, {"task_id": "live", "status": "running"})
        write_organizational(
            self.store,
            {"pattern_id": "keep", "description": "stay", "evidence": ["AGENTS.md"]},
        )
        write_verified(self.store, {"id": "keep", "fact": "stay", "how": "unit"})
        old = MemoryEntry(
            key="session:old",
            layer=MemoryLayer.SESSION,
            entry_type=MemoryEntryType.GOAL_STATE,
            value={"session_id": "old", "live_verified": False},
            created_at=(datetime.now(timezone.utc) - timedelta(hours=48)).isoformat(),
        )
        self.store.put(old)
        result = apply_retention(self.store, session_max_age_hours=24.0)
        self.assertIn("session:old", result["expired_sessions"])
        self.assertIn("task:done", result["expired_tasks"])
        self.assertEqual(read_session(self.store, "fresh").key, "session:fresh")
        self.assertEqual(read_task(self.store, "live").value["status"], "running")
        self.assertEqual(result["organizational"], 1)
        self.assertEqual(result["verified_knowledge"], 1)
        self.assertFalse(result["live_verified"])


if __name__ == "__main__":
    unittest.main()
