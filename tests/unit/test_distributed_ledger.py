"""Unit tests for thinkbox/ledger/distributed — CRDT-based distributed ActionLedger."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from thinkbox.ledger import ActionLedger
from thinkbox.ledger.distributed import (
    CRDTEntry,
    DistributedActionLedger,
    MergeOperation,
    VectorClock,
)


class TestVectorClock(unittest.TestCase):
    def test_increment_self(self):
        vc = VectorClock("node_a")
        vc.increment()
        self.assertEqual(vc.counters, {"node_a": 1})

    def test_increment_other(self):
        vc = VectorClock("node_a")
        vc.increment("node_b")
        self.assertEqual(vc.counters, {"node_b": 1})

    def test_merge(self):
        vc1 = VectorClock("node_a")
        vc1.increment()
        vc1.increment("node_b")
        vc2 = VectorClock("node_a")
        vc2.increment("node_b")
        vc2.increment("node_c")
        vc1.merge(vc2)
        self.assertEqual(vc1.counters, {"node_a": 1, "node_b": 1, "node_c": 1})

    def test_dominates(self):
        vc1 = VectorClock("a")
        vc1.counters = {"a": 2, "b": 1}
        vc2 = VectorClock("a")
        vc2.counters = {"a": 1, "b": 1}
        self.assertTrue(vc1.dominates(vc2))
        self.assertFalse(vc2.dominates(vc1))

    def test_concurrent(self):
        vc1 = VectorClock("a")
        vc1.counters = {"a": 1, "b": 2}
        vc2 = VectorClock("a")
        vc2.counters = {"a": 2, "b": 1}
        self.assertTrue(vc1.concurrent_with(vc2))
        self.assertTrue(vc2.concurrent_with(vc1))

    def test_snapshot(self):
        vc = VectorClock("node_x")
        vc.counters = {"node_x": 3, "node_y": 1}
        snap = vc.snapshot()
        self.assertEqual(snap, {"node_id": "node_x", "counters": {"node_x": 3, "node_y": 1}})


class TestCRDTEntry(unittest.TestCase):
    def test_creation(self):
        entry = CRDTEntry(
            entry_id="e1",
            agent_id="agent_1",
            capability="file:read",
            action="read",
            allowed=True,
            reason="ok",
            timestamp="2026-09-19T12:00:00+00:00",
            prev_hash="GENESIS",
            entry_hash="abc123",
            node_id="node_a",
            vector_clock={"node_a": 1},
        )
        self.assertEqual(entry.entry_id, "e1")
        self.assertTrue(entry.allowed)
        self.assertEqual(entry.node_id, "node_a")


class TestDistributedActionLedger(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.local_db = os.path.join(self.tmpdir, "ledger.db")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_append_basic(self):
        ledger = DistributedActionLedger(node_id="node_a")
        entry = ledger.append(
            agent_id="agent_1",
            capability="file:read",
            action="read",
            allowed=True,
            reason="ok",
        )
        self.assertEqual(entry.node_id, "node_a")
        self.assertNotEqual(entry.entry_hash, "")
        self.assertEqual(ledger.entry_count(), 1)

    def test_append_with_local_ledger(self):
        ledger = DistributedActionLedger(
            node_id="node_a",
            local_db_path=self.local_db,
        )
        entry = ledger.append(
            agent_id="agent_1",
            capability="file:read",
            action="read",
            allowed=True,
            reason="ok",
        )
        self.assertNotEqual(entry.entry_hash, "")
        self.assertTrue(ledger.verify_local_chain())

    def test_append_without_local_ledger(self):
        ledger = DistributedActionLedger(node_id="node_a")
        entry = ledger.append(
            agent_id="agent_1",
            capability="file:read",
            action="read",
            allowed=True,
            reason="ok",
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry.node_id, "node_a")

    def test_get_entries_filter_by_agent(self):
        ledger = DistributedActionLedger(node_id="node_a")
        ledger.append("agent_1", "file:read", "read", True, "ok")
        ledger.append("agent_2", "file:write", "write", True, "ok")
        entries = ledger.get_entries(agent_id="agent_1")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["agent_id"], "agent_1")

    def test_get_entries_filter_by_node(self):
        ledger_a = DistributedActionLedger(node_id="node_a")
        ledger_b = DistributedActionLedger(node_id="node_b")
        ledger_a.append("agent_1", "file:read", "read", True, "ok")
        ledger_b.append("agent_2", "file:write", "write", True, "ok")
        entries_a = ledger_a.get_entries(node_id="node_a")
        entries_b = ledger_a.get_entries(node_id="node_b")
        self.assertEqual(len(entries_a), 1)
        self.assertEqual(len(entries_b), 0)

    def test_merge_basic(self):
        ledger_a = DistributedActionLedger(node_id="node_a")
        ledger_b = DistributedActionLedger(node_id="node_b")
        entry_a = ledger_a.append("agent_1", "file:read", "read", True, "ok")
        accepted = ledger_b.merge([entry_a])
        self.assertEqual(len(accepted), 1)
        self.assertEqual(ledger_b.entry_count(), 1)

    def test_merge_concurrent_entries(self):
        ledger_a = DistributedActionLedger(node_id="node_a")
        ledger_b = DistributedActionLedger(node_id="node_b")
        entry_a = ledger_a.append("agent_1", "file:read", "read", True, "ok")
        entry_b = ledger_b.append("agent_1", "file:write", "write", True, "ok")
        accepted_a = ledger_a.merge([entry_b])
        accepted_b = ledger_b.merge([entry_a])
        self.assertTrue(len(accepted_a) >= 1)
        self.assertTrue(len(accepted_b) >= 1)

    def test_merge_duplicate_entry(self):
        ledger_a = DistributedActionLedger(node_id="node_a")
        ledger_b = DistributedActionLedger(node_id="node_b")
        entry_a = ledger_a.append("agent_1", "file:read", "read", True, "ok")
        ledger_b.merge([entry_a])
        accepted = ledger_a.merge([entry_a])
        self.assertEqual(len(accepted), 0)

    def test_anchor_without_local_ledger(self):
        ledger = DistributedActionLedger(node_id="node_a")
        result = ledger.anchor()
        self.assertIsNone(result)

    def test_anchor_with_local_ledger(self):
        ledger = DistributedActionLedger(
            node_id="node_a",
            local_db_path=self.local_db,
        )
        ledger.append("agent_1", "file:read", "read", True, "ok")
        anchor_hash = ledger.anchor()
        self.assertIsNotNone(anchor_hash)
        self.assertEqual(ledger.anchor_count(), 1)

    def test_vector_clock_after_append(self):
        ledger = DistributedActionLedger(node_id="node_a")
        ledger.append("agent_1", "file:read", "read", True, "ok")
        vc = ledger.vector_clock
        self.assertEqual(vc.get("node_a", 0), 1)

    def test_entry_count(self):
        ledger = DistributedActionLedger(node_id="node_a")
        self.assertEqual(ledger.entry_count(), 0)
        ledger.append("a", "c", "act", True, "r")
        ledger.append("b", "c2", "act2", True, "r2")
        self.assertEqual(ledger.entry_count(), 2)

    def test_get_entries_limit(self):
        ledger = DistributedActionLedger(node_id="node_a")
        for i in range(5):
            ledger.append(f"agent_{i}", "file:read", "read", True, "ok")
        entries = ledger.get_entries(limit=2)
        self.assertEqual(len(entries), 2)

    def test_get_entries_empty(self):
        ledger = DistributedActionLedger(node_id="node_a")
        entries = ledger.get_entries()
        self.assertEqual(len(entries), 0)

    def test_merge_operations(self):
        ledger = DistributedActionLedger(node_id="node_a")
        ops = ledger.merge_operations()
        self.assertEqual(len(ops), 0)


class TestLocalLedgerIntegration(unittest.TestCase):
    def test_local_ledger_actionledger_compatible(self):
        ld = DistributedActionLedger(node_id="node_a", local_db_path=":memory:")
        entry = ld.append("agent_1", "file:read", "read", True, "ok")
        self.assertTrue(ld.verify_local_chain())

    def test_local_ledger_entries_through_crdt(self):
        ld = DistributedActionLedger(node_id="node_a", local_db_path=":memory:")
        ld.append("agent_1", "file:read", "read", True, "ok")
        ld.append("agent_2", "file:write", "write", True, "ok")
        self.assertTrue(ld.verify_local_chain())
        entries = ld.local_ledger.entries()
        self.assertEqual(len(entries), 2)
