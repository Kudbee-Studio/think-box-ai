"""Hermetic tests for durable autonomous-loop action receipts (PR #251).

Loop actions previously lived only in DashboardState's in-memory dict and were
lost on restart. These tests verify the SQLite store's hash-chain integrity,
per-loop filtering, restart survival, tamper detection, and the dashboard wiring.

Covers:
- LoopActionReceipt fields, defaults, to_dict
- append: genesis head, prev_hash linkage, evidence_label, result wrapping
- verify: valid chain; detects edited row / deleted row
- latest: newest-first ordering + limit
- by_loop: filters per loop, preserves order, respects limit
- count + empty store
- restart survival: reopening the same file preserves count and validity
- DashboardState integration: record_loop_action persists; survives reopen;
  no store attached => still works; storage failure does not break control flow
- build_chain_integrity_payload: attached true/false states
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any

from thinkbox.autonomous_loop_action_store import (
    GENESIS_HASH,
    LoopActionReceipt,
    LoopActionStore,
    default_loop_action_db_path,
    open_loop_action_store,
)
from thinkbox.dashboard_state import (
    AutonomousLoopEntry,
    DashboardState,
    LoopActionEntry,
    get_dashboard_state,
)
import thinkbox.dashboard_state as ds_mod


def _reset_dashboard() -> None:
    DashboardState._instance = None
    ds_mod._dashboard_state = None


class _TempDbMixin:
    def make_path(self) -> str:
        tmp = tempfile.mkdtemp()
        return str(Path(tmp) / "loop_actions.db")


class TestLoopActionReceiptModel(unittest.TestCase):
    def test_to_dict_roundtrip(self) -> None:
        receipt = LoopActionReceipt(
            receipt_id="lar_1",
            loop_id="loopA",
            action="start",
            source="ui",
            evidence_label="simulated",
            timestamp="2026-01-01T00:00:00Z",
            prev_hash=GENESIS_HASH,
            entry_hash="abc123",
            result={"a": 1},
            loop_action_id="act_1",
        )
        data = receipt.to_dict()
        self.assertEqual(data["receipt_id"], "lar_1")
        self.assertEqual(data["loop_id"], "loopA")
        self.assertEqual(data["action"], "start")
        self.assertEqual(data["result"], {"a": 1})
        self.assertEqual(data["loop_action_id"], "act_1")
        self.assertEqual(sorted(data.keys()), sorted(LoopActionReceipt(
            receipt_id="", loop_id="", action="", source="", evidence_label="",
            timestamp="", prev_hash="", entry_hash="",
        ).to_dict().keys()))


class TestLoopActionStoreAppend(unittest.TestCase, _TempDbMixin):
    def setUp(self) -> None:
        self.store = LoopActionStore()

    def tearDown(self) -> None:
        self.store.close()

    def test_empty_store(self) -> None:
        self.assertEqual(self.store.count(), 0)
        self.assertTrue(self.store.verify())
        self.assertEqual(self.store.latest(), [])
        self.assertEqual(self.store.by_loop("loopA"), [])

    def test_append_returns_receipt_with_expected_fields(self) -> None:
        receipt = self.store.append("loopA", "start", {"msg": "go"}, source="ui")
        self.assertIsInstance(receipt, LoopActionReceipt)
        self.assertEqual(receipt.loop_id, "loopA")
        self.assertEqual(receipt.action, "start")
        self.assertEqual(receipt.source, "ui")
        self.assertEqual(receipt.evidence_label, "simulated")
        self.assertTrue(receipt.receipt_id.startswith("lar_"))
        self.assertTrue(receipt.entry_hash)

    def test_first_receipt_prev_hash_is_genesis(self) -> None:
        receipt = self.store.append("loopA", "start")
        self.assertEqual(receipt.prev_hash, GENESIS_HASH)

    def test_prev_hash_links_to_previous_entry_hash(self) -> None:
        first = self.store.append("loopA", "start")
        second = self.store.append("loopA", "run")
        third = self.store.append("loopA", "stop")
        self.assertEqual(second.prev_hash, first.entry_hash)
        self.assertEqual(third.prev_hash, second.entry_hash)

    def test_result_dict_preserved(self) -> None:
        receipt = self.store.append("loopA", "run", {"n": 2})
        self.assertEqual(receipt.result, {"n": 2})

    def test_non_dict_result_wrapped(self) -> None:
        receipt = self.store.append("loopA", "run", 42)
        self.assertEqual(receipt.result, {"value": 42})

    def test_none_result_becomes_empty_dict(self) -> None:
        receipt = self.store.append("loopA", "run")
        self.assertEqual(receipt.result, {})

    def test_loop_action_id_recorded(self) -> None:
        receipt = self.store.append("loopA", "start", loop_action_id="act_xyz")
        self.assertEqual(receipt.loop_action_id, "act_xyz")
        self.assertEqual(self.store.by_loop("loopA")[0].loop_action_id, "act_xyz")

    def test_sequential_appends_increase_count(self) -> None:
        for action in ("start", "run", "stop"):
            self.store.append("loopA", action)
        self.assertEqual(self.store.count(), 3)


class TestLoopActionStoreVerify(unittest.TestCase, _TempDbMixin):
    def setUp(self) -> None:
        self.store = LoopActionStore()

    def tearDown(self) -> None:
        self.store.close()

    def test_verify_true_for_valid_chain(self) -> None:
        self.store.append("loopA", "start")
        self.store.append("loopA", "run")
        self.store.append("loopA", "stop")
        self.assertTrue(self.store.verify())

    def test_verify_detects_edited_action(self) -> None:
        path = self.make_path()
        store = LoopActionStore(path)
        store.append("loopA", "start")
        store.append("loopA", "stop")
        store.close()

        conn = sqlite3.connect(path)
        conn.execute(
            "UPDATE loop_action_receipts SET action='tampered' WHERE action='start'"
        )
        conn.commit()
        conn.close()

        reopened = LoopActionStore(path)
        self.assertFalse(reopened.verify())
        reopened.close()

    def test_verify_detects_edited_result_payload(self) -> None:
        path = self.make_path()
        store = LoopActionStore(path)
        store.append("loopA", "run", {"amount": 1})
        store.close()

        conn = sqlite3.connect(path)
        conn.execute(
            "UPDATE loop_action_receipts SET result=? WHERE action='run'",
            (json.dumps({"amount": 999}),),
        )
        conn.commit()
        conn.close()

        reopened = LoopActionStore(path)
        self.assertFalse(reopened.verify())
        reopened.close()

    def test_verify_detects_deleted_row(self) -> None:
        path = self.make_path()
        store = LoopActionStore(path)
        store.append("loopA", "start")
        store.append("loopA", "run")
        store.append("loopA", "stop")
        store.close()

        conn = sqlite3.connect(path)
        conn.execute("DELETE FROM loop_action_receipts WHERE action='run'")
        conn.commit()
        conn.close()

        reopened = LoopActionStore(path)
        self.assertFalse(reopened.verify())
        reopened.close()

    def test_verify_detects_reordered_head(self) -> None:
        path = self.make_path()
        store = LoopActionStore(path)
        store.append("loopA", "start")
        store.append("loopA", "stop")
        store.close()

        conn = sqlite3.connect(path)
        rows = conn.execute(
            "SELECT entry_hash FROM loop_action_receipts ORDER BY rowid"
        ).fetchall()
        first_hash, second_hash = rows[0][0], rows[1][0]
        conn.execute(
            "UPDATE loop_action_receipts SET entry_hash=? WHERE entry_hash=?",
            (first_hash, second_hash),
        )
        conn.commit()
        conn.close()

        reopened = LoopActionStore(path)
        self.assertFalse(reopened.verify())
        reopened.close()


class TestLoopActionStoreQueries(unittest.TestCase):
    def setUp(self) -> None:
        self.store = LoopActionStore()
        self.store.append("loopA", "start")
        self.store.append("loopB", "reset")
        self.store.append("loopA", "run")

    def tearDown(self) -> None:
        self.store.close()

    def test_latest_newest_first(self) -> None:
        actions = [r.action for r in self.store.latest(10)]
        self.assertEqual(actions, ["run", "reset", "start"])

    def test_latest_respects_limit(self) -> None:
        actions = [r.action for r in self.store.latest(2)]
        self.assertEqual(actions, ["run", "reset"])

    def test_by_loop_filters_single_loop(self) -> None:
        actions = [r.action for r in self.store.by_loop("loopA")]
        self.assertEqual(actions, ["start", "run"])

    def test_by_loop_other_loop(self) -> None:
        actions = [r.action for r in self.store.by_loop("loopB")]
        self.assertEqual(actions, ["reset"])

    def test_by_loop_unknown_loop_empty(self) -> None:
        self.assertEqual(self.store.by_loop("nope"), [])

    def test_by_loop_respects_limit(self) -> None:
        self.assertEqual(len(self.store.by_loop("loopA", limit=1)), 1)

    def test_count(self) -> None:
        self.assertEqual(self.store.count(), 3)


class TestLoopActionStoreRestartSurvival(unittest.TestCase, _TempDbMixin):
    def test_actions_survive_reopen(self) -> None:
        path = self.make_path()
        store = LoopActionStore(path)
        store.append("loopA", "start")
        store.append("loopA", "run")
        store.close()

        reopened = LoopActionStore(path)
        self.assertEqual(reopened.count(), 2)
        self.assertTrue(reopened.verify())
        self.assertEqual([r.action for r in reopened.by_loop("loopA")], ["start", "run"])
        reopened.close()

    def test_path_property_and_default_path(self) -> None:
        store = LoopActionStore()
        self.assertEqual(store.path, ":memory:")
        store.close()
        self.assertTrue(str(default_loop_action_db_path()).endswith("loop_actions.db"))

    def test_open_loop_action_store_creates_parent(self) -> None:
        tmp = tempfile.mkdtemp()
        target = Path(tmp) / "nested" / "db.sqlite"
        store = open_loop_action_store(target)
        self.assertTrue(target.exists())
        store.append("loopA", "start")
        self.assertEqual(store.count(), 1)
        store.close()


class TestDashboardStatePersistence(unittest.TestCase, _TempDbMixin):
    def setUp(self) -> None:
        _reset_dashboard()
        self.state = DashboardState()
        self.state.upsert_autonomous_loop(AutonomousLoopEntry(loop_id="loopA"))

    def tearDown(self) -> None:
        _reset_dashboard()

    def test_no_store_attached_still_records(self) -> None:
        entry = self.state.record_loop_action("loopA", "start")
        self.assertIsInstance(entry, LoopActionEntry)
        self.assertIsNone(self.state.get_loop_action_store())
        self.assertEqual(len(self.state.get_loop_actions("loopA")), 1)

    def test_record_persists_receipt(self) -> None:
        store = LoopActionStore()
        self.state.set_loop_action_store(store)
        self.state.record_loop_action("loopA", "start", {"k": 1})

        receipts = store.by_loop("loopA")
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0].action, "start")
        self.assertTrue(store.verify())

    def test_record_links_loop_action_id(self) -> None:
        store = LoopActionStore()
        self.state.set_loop_action_store(store)
        entry = self.state.record_loop_action("loopA", "run")

        self.assertEqual(store.by_loop("loopA")[0].loop_action_id, entry.action_id)

    def test_persisted_chain_survives_reopen(self) -> None:
        path = self.make_path()
        store = LoopActionStore(path)
        self.state.set_loop_action_store(store)
        self.state.record_loop_action("loopA", "start")
        self.state.record_loop_action("loopA", "stop")
        store.close()

        reopened = LoopActionStore(path)
        self.assertEqual(reopened.count(), 2)
        self.assertTrue(reopened.verify())
        reopened.close()

    def test_storage_failure_does_not_break_control_flow(self) -> None:
        class BrokenStore:
            def append(self, **_: Any) -> Any:
                raise RuntimeError("disk full")

        self.state.set_loop_action_store(BrokenStore())
        entry = self.state.record_loop_action("loopA", "start")
        self.assertIsInstance(entry, LoopActionEntry)
        self.assertEqual(self.state.autonomous_loops["loopA"].last_action, "start")
        self.assertEqual(len(self.state.get_loop_actions("loopA")), 1)

    def test_detach_store(self) -> None:
        store = LoopActionStore()
        self.state.set_loop_action_store(store)
        self.assertIsNotNone(self.state.get_loop_action_store())
        self.state.set_loop_action_store(None)
        self.assertIsNone(self.state.get_loop_action_store())
        store.close()


class TestIntegrityPayload(unittest.TestCase):
    def setUp(self) -> None:
        _reset_dashboard()

    def tearDown(self) -> None:
        _reset_dashboard()

    def test_payload_when_no_store_attached(self) -> None:
        from backend.api.v1.autonomous_loop import build_chain_integrity_payload

        state = get_dashboard_state()
        payload = build_chain_integrity_payload(state)
        self.assertFalse(payload["attached"])
        self.assertEqual(payload["count"], 0)
        self.assertIsNone(payload["valid"])
        self.assertEqual(payload["latest"], [])

    def test_payload_when_store_attached(self) -> None:
        from backend.api.v1.autonomous_loop import build_chain_integrity_payload

        state = get_dashboard_state()
        store = LoopActionStore()
        state.set_loop_action_store(store)
        state.record_loop_action("loopA", "start")

        payload = build_chain_integrity_payload(state)
        self.assertTrue(payload["attached"])
        self.assertEqual(payload["count"], 1)
        self.assertTrue(payload["valid"])
        self.assertEqual([r["action"] for r in payload["latest"]], ["start"])
        store.close()

    def test_payload_reports_invalid_chain(self) -> None:
        from backend.api.v1.autonomous_loop import build_chain_integrity_payload

        state = get_dashboard_state()
        store = LoopActionStore()
        state.set_loop_action_store(store)
        state.record_loop_action("loopA", "start")
        store._conn.execute(  # tamper directly
            "UPDATE loop_action_receipts SET action='bad'"
        )
        store._conn.commit()

        payload = build_chain_integrity_payload(state)
        self.assertFalse(payload["valid"])
        store.close()


if __name__ == "__main__":
    unittest.main()
